import React, { useState, useEffect } from 'react';
import { useData, GroupSummary } from '../contexts/DataContext';
import { api, GroupDetail } from '../../services/api';
import { Button } from '../components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
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
import { Badge } from '../components/ui/badge';
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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-white">Groups</h1>
          <p className="text-gray-400 mt-1">
            Manage permission groups and their members
          </p>
        </div>
        <Button onClick={openCreateDialog} className="gap-2">
          <Plus className="h-4 w-4" />
          Create Group
        </Button>
      </div>

      <Alert className="bg-purple-950 border-purple-900">
        <Info className="h-4 w-4 text-purple-400" />
        <AlertDescription className="text-purple-300">
          Group permissions override domain defaults. When a user belongs to multiple groups,
          the most permissive setting wins. User-level overrides take precedence over group permissions.
        </AlertDescription>
      </Alert>

      <Card className="bg-gray-900 border-gray-800">
        <CardHeader>
          <CardTitle className="text-white">All Groups</CardTitle>
          <CardDescription className="text-gray-400">
            Click a group to manage its permissions and members
          </CardDescription>
        </CardHeader>
        <CardContent>
          {groups.length === 0 ? (
            <p className="text-gray-500 text-center py-8">
              No groups created yet. Click "Create Group" to get started.
            </p>
          ) : (
            <div className="border border-gray-800 rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="border-gray-800 hover:bg-gray-800/50">
                    <TableHead className="text-gray-300">Group</TableHead>
                    <TableHead className="text-gray-300">Members</TableHead>
                    <TableHead className="text-gray-300">Permissions</TableHead>
                    <TableHead className="text-right text-gray-300">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {groups.map((group) => (
                    <TableRow
                      key={group.id}
                      className="border-gray-800 hover:bg-gray-800/50 cursor-pointer"
                      onClick={() => openDetailDialog(group)}
                    >
                      <TableCell className="font-medium text-white">
                        <div>
                          <div className="flex items-center gap-2">
                            <UsersRound className="h-4 w-4 text-purple-400" />
                            {group.name}
                          </div>
                          {group.description && (
                            <p className="text-sm text-gray-500 mt-1">{group.description}</p>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-gray-300 border-gray-700">
                          {group.memberCount} {group.memberCount === 1 ? 'member' : 'members'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-purple-300 border-purple-800">
                          {group.permissionCount} {group.permissionCount === 1 ? 'rule' : 'rules'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2" onClick={(e) => e.stopPropagation()}>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openDetailDialog(group)}
                            className="text-gray-400 hover:text-white"
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(group)}
                            className="text-gray-400 hover:text-red-400"
                          >
                            <Trash2 className="h-4 w-4" />
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
        <DialogContent className="bg-gray-900 border-gray-800">
          <DialogHeader>
            <DialogTitle className="text-white">Create Group</DialogTitle>
            <DialogDescription className="text-gray-400">
              Create a new permission group. You can add members and permissions after creation.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label className="text-gray-300">Group Name</Label>
              <Input
                value={groupName}
                onChange={(e) => setGroupName(e.target.value)}
                placeholder="e.g. Engineering"
                className="bg-gray-800 border-gray-700 text-white"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-gray-300">Description (optional)</Label>
              <Input
                value={groupDescription}
                onChange={(e) => setGroupDescription(e.target.value)}
                placeholder="e.g. Engineering team members"
                className="bg-gray-800 border-gray-700 text-white"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)} className="border-gray-700 text-gray-300">
              Cancel
            </Button>
            <Button onClick={handleCreate}>Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Group Detail Dialog */}
      <Dialog open={showDetailDialog} onOpenChange={setShowDetailDialog}>
        <DialogContent className="bg-gray-900 border-gray-800 max-w-3xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-white flex items-center gap-2">
              <UsersRound className="h-5 w-5 text-purple-400" />
              {selectedGroup?.name}
            </DialogTitle>
            <DialogDescription className="text-gray-400">
              Manage group settings, permissions, and members
            </DialogDescription>
          </DialogHeader>

          {/* Metadata section */}
          <div className="space-y-4 py-2 border-b border-gray-800 pb-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-gray-300">Group Name</Label>
                <Input
                  value={groupName}
                  onChange={(e) => setGroupName(e.target.value)}
                  className="bg-gray-800 border-gray-700 text-white"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-gray-300">Description</Label>
                <Input
                  value={groupDescription}
                  onChange={(e) => setGroupDescription(e.target.value)}
                  className="bg-gray-800 border-gray-700 text-white"
                />
              </div>
            </div>
            <Button size="sm" onClick={handleSaveMetadata}>Save Details</Button>
          </div>

          {/* Tab switcher */}
          <div className="flex gap-2 pt-2">
            <Button
              variant={activeTab === 'permissions' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setActiveTab('permissions')}
              className={activeTab !== 'permissions' ? 'border-gray-700 text-gray-300' : ''}
            >
              <ShieldCheck className="h-4 w-4 mr-1" />
              Permissions
            </Button>
            <Button
              variant={activeTab === 'members' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setActiveTab('members')}
              className={activeTab !== 'members' ? 'border-gray-700 text-gray-300' : ''}
            >
              <UserPlus className="h-4 w-4 mr-1" />
              Members
            </Button>
          </div>

          {/* Permissions tab */}
          {activeTab === 'permissions' && (
            <div className="space-y-3">
              <div className="border border-gray-800 rounded-lg overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow className="border-gray-800">
                      <TableHead className="text-gray-300">Folder</TableHead>
                      <TableHead className="text-gray-300 w-20 text-center">Read</TableHead>
                      <TableHead className="text-gray-300 w-20 text-center">Write</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {allFolders.map((folder) => {
                      const perm = getPermission(folder.path);
                      return (
                        <TableRow key={folder.path} className="border-gray-800">
                          <TableCell className="text-white">
                            <div className="flex items-center gap-2">
                              <FolderOpen className="h-4 w-4 text-gray-400" />
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
              <Button onClick={handleSavePermissions}>Save Permissions</Button>
            </div>
          )}

          {/* Members tab */}
          {activeTab === 'members' && (
            <div className="space-y-3">
              <div className="border border-gray-800 rounded-lg overflow-hidden max-h-[40vh] overflow-y-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="border-gray-800">
                      <TableHead className="text-gray-300 w-12"></TableHead>
                      <TableHead className="text-gray-300">User</TableHead>
                      <TableHead className="text-gray-300">Role</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {users.map((user) => (
                      <TableRow key={user.id} className="border-gray-800">
                        <TableCell>
                          <Checkbox
                            checked={memberIds.has(user.id)}
                            onCheckedChange={() => toggleMember(user.id)}
                          />
                        </TableCell>
                        <TableCell className="text-white">{user.email}</TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={user.role === 'admin' ? 'text-orange-300 border-orange-800' : 'text-gray-300 border-gray-700'}
                          >
                            {user.role}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <Button onClick={handleSaveMembers}>Save Members</Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
