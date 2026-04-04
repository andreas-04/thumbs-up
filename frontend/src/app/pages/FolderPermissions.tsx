import React, { useState, useEffect } from 'react';
import { useData, User, FolderPermission } from '../contexts/DataContext';
import { api, PermissionState, EffectivePermissions, EffectivePermissionEntry } from '../../services/api';
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
import { Label } from '../components/ui/label';
import { 
  FolderOpen, 
  Edit, 
  Info,
  CheckCircle,
  XCircle,
  MinusCircle,
  Mail,
  User as UserIcon,
  Eye,
} from 'lucide-react';
import { toast } from 'sonner';

/** Cycle through the three permission states: null → allow → deny → null */
function nextPermState(current: PermissionState): PermissionState {
  if (current === null) return 'allow';
  if (current === 'allow') return 'deny';
  return null; // deny → null
}

function PermStateBadge({ value }: { value: PermissionState }) {
  if (value === 'allow') {
    return (
      <span className="inline-flex items-center gap-1 text-term-green text-xs">
        <CheckCircle className="h-3 w-3" /> allow
      </span>
    );
  }
  if (value === 'deny') {
    return (
      <span className="inline-flex items-center gap-1 text-term-red text-xs">
        <XCircle className="h-3 w-3" /> deny
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-muted-foreground text-xs">
      <MinusCircle className="h-3 w-3" /> --
    </span>
  );
}

export default function FolderPermissions() {
  const { settings, users, refreshUsers, updateUserPermissions } = useData();
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [permissions, setPermissions] = useState<FolderPermission[]>([]);
  const [allFolders, setAllFolders] = useState<Array<{ path: string; name: string }>>([]);
  const [showEffectiveDialog, setShowEffectiveDialog] = useState(false);
  const [effectiveUser, setEffectiveUser] = useState<User | null>(null);
  const [effectivePerms, setEffectivePerms] = useState<EffectivePermissions>({});

  useEffect(() => {
    refreshUsers().catch((err) => console.error('Failed to refresh users:', err));
    api.listFolders()
      .then(({ folders }) => setAllFolders(folders))
      .catch((err) => console.error('Failed to load folders:', err));
  }, [refreshUsers]);

  const openEditDialog = (user: User) => {
    setSelectedUser(user);
    setPermissions([...user.folderPermissions]);
    setShowEditDialog(true);
  };

  const openEffectiveDialog = async (user: User) => {
    setEffectiveUser(user);
    try {
      const { permissions } = await api.getEffectivePermissions(user.id);
      setEffectivePerms(permissions);
      setShowEffectiveDialog(true);
    } catch (err) {
      toast.error('Failed to load effective permissions');
    }
  };

  const handlePermissionCycle = (folderPath: string, permType: 'read' | 'write') => {
    setPermissions((prev) => {
      const existing = prev.find((p) => p.path === folderPath);
      
      if (existing) {
        const newVal = nextPermState(existing[permType]);
        const updated = prev.map((p) =>
          p.path === folderPath ? { ...p, [permType]: newVal } : p
        );
        // Remove the entry entirely if both flags are back to null
        return updated.filter((p) => p.read !== null || p.write !== null);
      } else {
        // First click → create with 'allow' on the toggled type, null on the other
        return [
          ...prev,
          {
            id: 0,
            userId: 0,
            path: folderPath,
            read: permType === 'read' ? 'allow' as PermissionState : null,
            write: permType === 'write' ? 'allow' as PermissionState : null,
            createdAt: new Date().toISOString(),
          },
        ];
      }
    });
  };

  const getPermission = (folderPath: string): FolderPermission | null => {
    return permissions.find((p) => p.path === folderPath) || null;
  };

  const handleSave = async () => {
    if (!selectedUser) return;

    // Only send rows where at least one flag is set (allow or deny)
    const cleanedPermissions = permissions
      .filter((p) => p.read !== null || p.write !== null)
      .map((p) => ({ path: p.path, read: p.read, write: p.write }));

    try {
      await updateUserPermissions(selectedUser.id, cleanedPermissions);
      toast.success('Folder permissions updated successfully');
      setShowEditDialog(false);
      setSelectedUser(null);
      setPermissions([]);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update permissions');
    }
  };

  if (!settings) {
    return null;
  }

  const getUserIdentifier = (user: User): string => {
    if (settings.authMethod === 'username+password') {
      return user.username || 'N/A';
    }
    return user.email || 'N/A';
  };

  if (users.length === 0) {
    return (
      <div className="space-y-4">
        <div>
          <h1 className="text-lg text-foreground">folder permissions</h1>
          <p className="text-muted-foreground text-xs mt-1">
            per-user folder access control
          </p>
        </div>

        <Alert className="glass border-glass-border">
          <Info className="h-3.5 w-3.5 text-term-blue" />
          <AlertDescription className="text-muted-foreground text-xs">
            no users yet. add users in <a href="/admin/users" className="text-term-blue underline">user management</a> first.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg text-foreground">folder permissions</h1>
        <p className="text-muted-foreground text-xs mt-1">
          per-user folder access control
        </p>
      </div>

      <Card className="glass">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm text-foreground">user permissions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="border border-glass-border rounded overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="border-glass-border hover:bg-glass-highlight">
                  <TableHead className="text-muted-foreground text-xs">user</TableHead>
                  <TableHead className="text-muted-foreground text-xs hidden sm:table-cell">permissions</TableHead>
                  <TableHead className="text-right text-muted-foreground text-xs"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((user) => (
                  <TableRow key={user.id} className="border-glass-border hover:bg-glass-highlight">
                    <TableCell className="text-foreground text-xs">
                      <div className="flex items-center gap-1.5">
                        {settings.authMethod === 'username+password' ? (
                          <UserIcon className="h-3.5 w-3.5 text-muted-foreground" />
                        ) : (
                          <Mail className="h-3.5 w-3.5 text-muted-foreground" />
                        )}
                        {getUserIdentifier(user)}
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-xs hidden sm:table-cell">
                      {user.folderPermissions.length === 0 ? (
                        <span className="text-term-dim">none</span>
                      ) : (
                        <span>
                          {user.folderPermissions.slice(0, 2).map((perm) => (
                            <span key={perm.path} className="mr-2">
                              {perm.path}: {perm.read === 'allow' ? 'r' : perm.read === 'deny' ? '!r' : ''}{perm.write === 'allow' ? 'w' : perm.write === 'deny' ? '!w' : ''}
                            </span>
                          ))}
                          {user.folderPermissions.length > 2 && (
                            <span className="text-term-dim">+{user.folderPermissions.length - 2}</span>
                          )}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEffectiveDialog(user)}
                          className="text-term-purple hover:text-term-cyan h-7 text-xs"
                        >
                          <Eye className="h-3.5 w-3.5 mr-1" />
                          effective
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEditDialog(user)}
                          className="text-term-blue hover:text-term-cyan h-7 text-xs"
                        >
                          <Edit className="h-3.5 w-3.5 mr-1" />
                          edit
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Edit Permissions Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent className="glass border-glass-border max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-foreground text-sm">
              edit user overrides
            </DialogTitle>
            <DialogDescription className="text-muted-foreground text-xs">
              configure overrides for <strong className="text-foreground">{selectedUser && getUserIdentifier(selectedUser)}</strong>
            </DialogDescription>
          </DialogHeader>
          
          <div className="py-3">
            <Alert className="glass border-glass-border mb-3">
              <Info className="h-3.5 w-3.5 text-muted-foreground" />
              <AlertDescription className="text-muted-foreground text-xs">
                click to cycle: <span className="text-term-green">allow</span> / <span className="text-term-red">deny</span> / <span className="text-muted-foreground">inherit</span>
              </AlertDescription>
            </Alert>

            <div className="space-y-1">
              <Label className="text-muted-foreground text-xs">folder access</Label>
              <div className="border border-glass-border rounded overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow className="border-glass-border hover:bg-glass-highlight">
                      <TableHead className="text-muted-foreground text-xs">folder</TableHead>
                      <TableHead className="text-center text-muted-foreground text-xs">read</TableHead>
                      <TableHead className="text-center text-muted-foreground text-xs">write</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {allFolders.map((folder) => {
                      const perm = getPermission(folder.path);
                      return (
                        <TableRow key={folder.path} className="border-glass-border">
                          <TableCell className="text-foreground text-xs">
                            <div className="flex items-center gap-1.5">
                              <FolderOpen className="h-3.5 w-3.5 text-term-yellow" />
                              {folder.name}
                              <span className="text-term-dim text-[10px]">{folder.path}</span>
                            </div>
                          </TableCell>
                          <TableCell className="text-center">
                            <button
                              type="button"
                              onClick={() => handlePermissionCycle(folder.path, 'read')}
                              className="inline-flex items-center justify-center w-16 h-7 rounded border border-glass-border hover:border-foreground/30 transition-colors glass"
                            >
                              <PermStateBadge value={perm?.read ?? null} />
                            </button>
                          </TableCell>
                          <TableCell className="text-center">
                            <button
                              type="button"
                              onClick={() => handlePermissionCycle(folder.path, 'write')}
                              className="inline-flex items-center justify-center w-16 h-7 rounded border border-glass-border hover:border-foreground/30 transition-colors glass"
                            >
                              <PermStateBadge value={perm?.write ?? null} />
                            </button>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button 
              variant="outline" 
              onClick={() => setShowEditDialog(false)}
              className="glass border-glass-border text-foreground h-8 text-xs"
            >
              cancel
            </Button>
            <Button onClick={handleSave} className="h-8 text-xs">
              save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Effective Permissions Dialog */}
      <Dialog open={showEffectiveDialog} onOpenChange={setShowEffectiveDialog}>
        <DialogContent className="glass border-glass-border max-w-4xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-foreground text-sm">
              effective permissions
            </DialogTitle>
            <DialogDescription className="text-muted-foreground text-xs">
              resolved for <strong className="text-foreground">{effectiveUser && getUserIdentifier(effectiveUser)}</strong> across all layers
            </DialogDescription>
          </DialogHeader>

          <div className="py-3">
            {Object.keys(effectivePerms).length === 0 ? (
              <Alert className="glass border-glass-border">
                <Info className="h-3.5 w-3.5 text-term-green" />
                <AlertDescription className="text-muted-foreground text-xs">
                  no permission rules configured. full access by default.
                </AlertDescription>
              </Alert>
            ) : (
              <div className="border border-glass-border rounded overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow className="border-glass-border">
                      <TableHead className="text-muted-foreground text-xs">path</TableHead>
                      <TableHead className="text-muted-foreground text-xs text-center">domain</TableHead>
                      <TableHead className="text-muted-foreground text-xs text-center">group</TableHead>
                      <TableHead className="text-muted-foreground text-xs text-center">user</TableHead>
                      <TableHead className="text-muted-foreground text-xs text-center">effective</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {Object.entries(effectivePerms)
                      .sort(([a], [b]) => a.localeCompare(b))
                      .map(([path, entry]) => (
                        <TableRow key={path} className="border-glass-border">
                          <TableCell className="text-foreground text-xs font-mono">
                            <div className="flex items-center gap-1.5">
                              <FolderOpen className="h-3.5 w-3.5 text-muted-foreground" />
                              {path}
                            </div>
                          </TableCell>
                          <TableCell className="text-center text-xs">
                            {entry.domain ? (
                              <span>
                                <span className={entry.domain.canRead ? 'text-term-blue' : 'text-term-dim'}>r</span>
                                <span className={entry.domain.canWrite ? 'text-term-blue' : 'text-term-dim'}>w</span>
                              </span>
                            ) : (
                              <span className="text-term-dim">--</span>
                            )}
                          </TableCell>
                          <TableCell className="text-center text-xs">
                            {entry.groupMerged ? (
                              <div>
                                <span className={entry.groupMerged.canRead ? 'text-term-purple' : 'text-term-dim'}>r</span>
                                <span className={entry.groupMerged.canWrite ? 'text-term-purple' : 'text-term-dim'}>w</span>
                                <div className="text-[10px] text-term-dim mt-0.5">
                                  {entry.groups.map((g) => g.groupName).join(', ')}
                                </div>
                              </div>
                            ) : (
                              <span className="text-term-dim">--</span>
                            )}
                          </TableCell>
                          <TableCell className="text-center text-xs">
                            {entry.user ? (
                              <span>
                                <span className={entry.user.canRead ? 'text-term-yellow' : 'text-term-dim'}>r</span>
                                <span className={entry.user.canWrite ? 'text-term-yellow' : 'text-term-dim'}>w</span>
                              </span>
                            ) : (
                              <span className="text-term-dim">--</span>
                            )}
                          </TableCell>
                          <TableCell className="text-center text-xs">
                            <span className={entry.effective.canRead ? 'text-term-green' : 'text-term-red'}>r</span>
                            <span className={entry.effective.canWrite ? 'text-term-green' : 'text-term-red'}>w</span>
                            <div className="text-[10px] text-term-dim mt-0.5">
                              via {entry.effective.source}
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </Table>
              </div>
            )}

            <div className="mt-3 flex gap-3 text-[10px] text-muted-foreground">
              <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-term-blue inline-block" /> domain</span>
              <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-term-purple inline-block" /> group</span>
              <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-term-yellow inline-block" /> user</span>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
