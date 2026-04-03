import React, { useState, useEffect } from 'react';
import { useData, GroupSummary } from '../contexts/DataContext';
import { api, GroupDetail } from '../../services/api';
import { Button } from '../components/ui/button';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '../components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Switch } from '../components/ui/switch';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { Checkbox } from '../components/ui/checkbox';
import {
  UsersRound,
  Plus,
  Edit,
  Trash2,
  Info,
  FolderOpen,
  ShieldCheck,
  UserPlus,
} from 'lucide-react';
import { toast } from 'sonner';

interface PermissionRow {
  path: string;
  read: boolean;
  write: boolean;
}

export default function GroupManagement() {
  const { groups, refreshGroups, users, refreshUsers } = useData();
  const [selectedGroup, setSelectedGroup] = useState<GroupDetail | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showDetailDialog, setShowDetailDialog] = useState(false);
  const [groupName, setGroupName] = useState('');
  const [groupDescription, setGroupDescription] = useState('');
  const [permissions, setPermissions] = useState<PermissionRow[]>([]);
  const [memberIds, setMemberIds] = useState<Set<number>>(new Set());
  const [allFolders, setAllFolders] = useState<Array<{ path: string; name: string }>>([]);
  const [activeTab, setActiveTab] = useState<'permissions' | 'members'>('permissions');

  useEffect(() => {
    refreshGroups().catch((err) => console.error('Failed to refresh groups:', err));
    refreshUsers().catch((err) => console.error('Failed to refresh users:', err));
    api.listFolders()
      .then(({ folders }) => setAllFolders(folders))
      .catch((err) => console.error('Failed to load folders:', err));
  }, [refreshGroups, refreshUsers]);

  const openCreateDialog = () => {
    setGroupName('');
    setGroupDescription('');
    setShowCreateDialog(true);
  };

  const openDetailDialog = async (group: GroupSummary) => {
    try {
      const { group: detail } = await api.getGroup(group.id);
      setSelectedGroup(detail);
      setGroupName(detail.name);
      setGroupDescription(detail.description || '');
      setPermissions(
        detail.permissions.map((p) => ({ path: p.path, read: p.read, write: p.write }))
      );
      setMemberIds(new Set(detail.members.map((m) => m.id)));
      setActiveTab('permissions');
      setShowDetailDialog(true);
    } catch (err) {
      toast.error('Failed to load group details');
    }
  };

  const handleCreate = async () => {
    if (!groupName.trim()) {
      toast.error('Group name is required');
      return;
    }
    try {
      await api.createGroup({
        name: groupName.trim(),
        description: groupDescription.trim() || undefined,
      });
      toast.success('Group created');
      await refreshGroups();
      setShowCreateDialog(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create group');
    }
  };

  const handlePermissionToggle = (folderPath: string, permType: 'read' | 'write') => {
    setPermissions((prev) => {
      const existing = prev.find((p) => p.path === folderPath);
      if (existing) {
        return prev.map((p) =>
          p.path === folderPath ? { ...p, [permType]: !p[permType] } : p
        );
      } else {
        return [
          ...prev,
          { path: folderPath, read: permType === 'read', write: permType === 'write' },
        ];
      }
    });
  };

  const toggleMember = (userId: number) => {
    setMemberIds((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) {
        next.delete(userId);
      } else {
        next.add(userId);
      }
      return next;
    });
  };

  const handleSavePermissions = async () => {
    if (!selectedGroup) return;
    const cleanedPermissions = permissions.filter((p) => p.read || p.write);
    try {
      await api.updateGroupPermissions(selectedGroup.id, cleanedPermissions);
      toast.success('Group permissions updated');
      await refreshGroups();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update permissions');
    }
  };

  const handleSaveMembers = async () => {
    if (!selectedGroup) return;
    try {
      const { group: updated } = await api.updateGroupMembers(
        selectedGroup.id,
        Array.from(memberIds)
      );
      setSelectedGroup(updated);
      toast.success('Group members updated');
      await refreshGroups();
      await refreshUsers();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update members');
    }
  };

  const handleSaveMetadata = async () => {
    if (!selectedGroup) return;
    try {
      await api.updateGroup(selectedGroup.id, {
        name: groupName.trim(),
        description: groupDescription.trim() || undefined,
      });
      toast.success('Group updated');
      await refreshGroups();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update group');
    }
  };

  const handleDelete = async (group: GroupSummary) => {
    try {
      await api.deleteGroup(group.id);
      toast.success(`Group "${group.name}" deleted`);
      await refreshGroups();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete group');
    }
  };

  const getPermission = (folderPath: string): PermissionRow | undefined => {
    return permissions.find((p) => p.path === folderPath);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg text-foreground">groups</h1>
          <p className="text-muted-foreground text-xs mt-1">
            manage permission groups and members
          </p>
        </div>
        <Button onClick={openCreateDialog} size="sm" className="gap-1.5 h-7 text-xs">
          <Plus className="h-3.5 w-3.5" />
          create group
        </Button>
      </div>

      <Alert className="glass border-glass-border">
        <Info className="h-3.5 w-3.5 text-term-purple" />
        <AlertDescription className="text-muted-foreground text-xs">
          group permissions override domain defaults. most permissive setting wins across groups. user-level overrides take precedence.
        </AlertDescription>
      </Alert>

      <Card className="glass">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm text-foreground">all groups</CardTitle>
        </CardHeader>
        <CardContent>
          {groups.length === 0 ? (
            <p className="text-muted-foreground text-center py-6 text-xs">
              no groups yet.
            </p>
          ) : (
            <div className="border border-glass-border rounded overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="border-glass-border hover:bg-glass-highlight">
                    <TableHead className="text-muted-foreground text-xs">group</TableHead>
                    <TableHead className="text-muted-foreground text-xs hidden sm:table-cell">members</TableHead>
                    <TableHead className="text-muted-foreground text-xs hidden sm:table-cell">rules</TableHead>
                    <TableHead className="text-right text-muted-foreground text-xs"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {groups.map((group) => (
                    <TableRow
                      key={group.id}
                      className="border-glass-border hover:bg-glass-highlight cursor-pointer"
                      onClick={() => openDetailDialog(group)}
                    >
                      <TableCell className="text-foreground text-xs">
                        <div>
                          <div className="flex items-center gap-1.5">
                            <UsersRound className="h-3.5 w-3.5 text-term-purple" />
                            {group.name}
                          </div>
                          {group.description && (
                            <p className="text-[10px] text-muted-foreground mt-0.5">{group.description}</p>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-xs hidden sm:table-cell">
                        {group.memberCount}
                      </TableCell>
                      <TableCell className="text-term-purple text-xs hidden sm:table-cell">
                        {group.permissionCount}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openDetailDialog(group)}
                            className="text-muted-foreground hover:text-foreground h-7 w-7 p-0"
                          >
                            <Edit className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(group)}
                            className="text-muted-foreground hover:text-term-red h-7 w-7 p-0"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create Group Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="glass border-glass-border">
          <DialogHeader>
            <DialogTitle className="text-foreground text-sm">create group</DialogTitle>
            <DialogDescription className="text-muted-foreground text-xs">
              add members and permissions after creation.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-3">
            <div className="space-y-1">
              <Label className="text-muted-foreground text-xs">group name</Label>
              <Input
                value={groupName}
                onChange={(e) => setGroupName(e.target.value)}
                placeholder="engineering"
                className="glass border-glass-border text-foreground h-8 text-xs"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-muted-foreground text-xs">description</Label>
              <Input
                value={groupDescription}
                onChange={(e) => setGroupDescription(e.target.value)}
                placeholder="optional"
                className="glass border-glass-border text-foreground h-8 text-xs"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)} className="glass border-glass-border text-foreground h-8 text-xs">
              cancel
            </Button>
            <Button onClick={handleCreate} className="h-8 text-xs">create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Group Detail Dialog */}
      <Dialog open={showDetailDialog} onOpenChange={setShowDetailDialog}>
        <DialogContent className="glass border-glass-border max-w-3xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-foreground text-sm flex items-center gap-1.5">
              <UsersRound className="h-3.5 w-3.5 text-term-purple" />
              {selectedGroup?.name}
            </DialogTitle>
            <DialogDescription className="text-muted-foreground text-xs">
              manage permissions and members
            </DialogDescription>
          </DialogHeader>

          {/* Metadata */}
          <div className="space-y-3 py-2 border-b border-glass-border pb-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="text-muted-foreground text-xs">name</Label>
                <Input
                  value={groupName}
                  onChange={(e) => setGroupName(e.target.value)}
                  className="glass border-glass-border text-foreground h-8 text-xs"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-muted-foreground text-xs">description</Label>
                <Input
                  value={groupDescription}
                  onChange={(e) => setGroupDescription(e.target.value)}
                  className="glass border-glass-border text-foreground h-8 text-xs"
                />
              </div>
            </div>
            <Button size="sm" onClick={handleSaveMetadata} className="h-7 text-xs">save details</Button>
          </div>

          {/* Tab switcher */}
          <div className="flex gap-1.5 pt-2">
            <Button
              variant={activeTab === 'permissions' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setActiveTab('permissions')}
              className={`h-7 text-xs ${activeTab !== 'permissions' ? 'glass border-glass-border text-foreground' : ''}`}
            >
              <ShieldCheck className="h-3.5 w-3.5 mr-1" />
              permissions
            </Button>
            <Button
              variant={activeTab === 'members' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setActiveTab('members')}
              className={`h-7 text-xs ${activeTab !== 'members' ? 'glass border-glass-border text-foreground' : ''}`}
            >
              <UserPlus className="h-3.5 w-3.5 mr-1" />
              members
            </Button>
          </div>

          {/* Permissions tab */}
          {activeTab === 'permissions' && (
            <div className="space-y-3">
              <div className="border border-glass-border rounded overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow className="border-glass-border">
                      <TableHead className="text-muted-foreground text-xs">folder</TableHead>
                      <TableHead className="text-muted-foreground text-xs w-16 text-center">read</TableHead>
                      <TableHead className="text-muted-foreground text-xs w-16 text-center">write</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {allFolders.map((folder) => {
                      const perm = getPermission(folder.path);
                      return (
                        <TableRow key={folder.path} className="border-glass-border">
                          <TableCell className="text-foreground text-xs">
                            <div className="flex items-center gap-1.5">
                              <FolderOpen className="h-3.5 w-3.5 text-muted-foreground" />
                              {folder.path}
                            </div>
                          </TableCell>
                          <TableCell className="text-center">
                            <Switch
                              checked={perm?.read ?? false}
                              onCheckedChange={() => handlePermissionToggle(folder.path, 'read')}
                            />
                          </TableCell>
                          <TableCell className="text-center">
                            <Switch
                              checked={perm?.write ?? false}
                              onCheckedChange={() => handlePermissionToggle(folder.path, 'write')}
                            />
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
              <Button onClick={handleSavePermissions} size="sm" className="h-7 text-xs">save permissions</Button>
            </div>
          )}

          {/* Members tab */}
          {activeTab === 'members' && (
            <div className="space-y-3">
              <div className="border border-glass-border rounded overflow-hidden max-h-[40vh] overflow-y-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="border-glass-border">
                      <TableHead className="text-muted-foreground text-xs w-10"></TableHead>
                      <TableHead className="text-muted-foreground text-xs">user</TableHead>
                      <TableHead className="text-muted-foreground text-xs">role</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {users.map((user) => (
                      <TableRow key={user.id} className="border-glass-border">
                        <TableCell>
                          <Checkbox
                            checked={memberIds.has(user.id)}
                            onCheckedChange={() => toggleMember(user.id)}
                          />
                        </TableCell>
                        <TableCell className="text-foreground text-xs">{user.email}</TableCell>
                        <TableCell className="text-xs">
                          <span className={user.role === 'admin' ? 'text-term-yellow' : 'text-muted-foreground'}>
                            {user.role}
                          </span>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <Button onClick={handleSaveMembers} size="sm" className="h-7 text-xs">save members</Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
