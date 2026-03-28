import React, { useState, useEffect } from 'react';
import { useData, User, FolderPermission } from '../contexts/DataContext';
import { api, PermissionState, EffectivePermissions, EffectivePermissionEntry } from '../../services/api';
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
      <span className="inline-flex items-center gap-1 text-green-400 text-xs font-medium">
        <CheckCircle className="h-3 w-3" /> Allow
      </span>
    );
  }
  if (value === 'deny') {
    return (
      <span className="inline-flex items-center gap-1 text-red-400 text-xs font-medium">
        <XCircle className="h-3 w-3" /> Deny
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-gray-500 text-xs font-medium">
      <MinusCircle className="h-3 w-3" /> —
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
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-semibold text-white">Folder Permissions</h1>
          <p className="text-gray-400 mt-1">
            Configure per-user folder access control
          </p>
        </div>

        <Alert className="bg-blue-950 border-blue-900">
          <Info className="h-4 w-4 text-blue-400" />
          <AlertDescription className="text-blue-300">
            No users have been added yet. Add users in <a href="/admin/users" className="underline">User Management</a> before configuring folder permissions.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-white">Folder Permissions</h1>
        <p className="text-gray-400 mt-1">
          Configure per-user folder access control (ACL)
        </p>
      </div>

      <Alert className="bg-blue-950 border-blue-900">
        <Info className="h-4 w-4 text-blue-400" />
        <AlertDescription className="text-blue-300">
          <strong>Additive Permissions:</strong> Users have no access by default.
          Enable read/write toggles to grant access to specific folders.
          User-level permissions override domain and group settings.
        </AlertDescription>
      </Alert>

      <Card className="bg-gray-900 border-gray-800">
        <CardHeader>
          <CardTitle className="text-white">User Permissions</CardTitle>
          <CardDescription className="text-gray-400">
            Click "Edit" to configure folder-level access for each user
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="border border-gray-800 rounded-lg overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="border-gray-800 hover:bg-gray-800/50">
                  <TableHead className="text-gray-300">User</TableHead>
                  <TableHead className="text-gray-300">Permissions</TableHead>
                  <TableHead className="text-right text-gray-300">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((user) => (
                  <TableRow key={user.id} className="border-gray-800 hover:bg-gray-800/50">
                    <TableCell className="font-medium text-white">
                      <div className="flex items-center gap-2">
                        {settings.authMethod === 'username+password' ? (
                          <UserIcon className="h-4 w-4 text-gray-400" />
                        ) : (
                          <Mail className="h-4 w-4 text-gray-400" />
                        )}
                        {getUserIdentifier(user)}
                      </div>
                    </TableCell>
                    <TableCell className="text-gray-400">
                      <div className="flex flex-wrap gap-1">
                        {user.folderPermissions.length === 0 ? (
                          <Badge variant="outline" className="text-gray-400 border-gray-700">
                            No Direct Permissions
                          </Badge>
                        ) : (
                          user.folderPermissions.slice(0, 2).map((perm) => (
                            <Badge key={perm.path} variant="outline" className="text-gray-300 border-gray-700">
                              {perm.path}: {perm.read === 'allow' ? 'R' : perm.read === 'deny' ? '!R' : ''}{perm.write === 'allow' ? 'W' : perm.write === 'deny' ? '!W' : ''}
                            </Badge>
                          ))
                        )}
                        {user.folderPermissions.length > 2 && (
                          <Badge variant="outline" className="text-gray-400 border-gray-700">
                            +{user.folderPermissions.length - 2} more
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEffectiveDialog(user)}
                          className="text-purple-400 hover:text-purple-300"
                        >
                          <Eye className="h-4 w-4 mr-1" />
                          Effective
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEditDialog(user)}
                          className="text-blue-400 hover:text-blue-300"
                        >
                          <Edit className="h-4 w-4 mr-1" />
                          Edit
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
        <DialogContent className="bg-gray-900 border-gray-800 text-white max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-white">
              Edit User Overrides
            </DialogTitle>
            <DialogDescription className="text-gray-400">
              Configure user-level permission overrides for <strong>{selectedUser && getUserIdentifier(selectedUser)}</strong>. These take highest priority in the permission hierarchy.
            </DialogDescription>
          </DialogHeader>
          
          <div className="py-4">
            <Alert className="bg-gray-800 border-gray-700 mb-4">
              <Info className="h-4 w-4 text-gray-400" />
              <AlertDescription className="text-gray-300 text-sm">
                <strong>Tri-state permissions:</strong> Click the cells to cycle through:
                {' '}<span className="text-green-400">Allow</span> → <span className="text-red-400">Deny</span> → <span className="text-gray-500">No Action</span> (inherits from group/domain).
              </AlertDescription>
            </Alert>

            <div className="space-y-2">
              <Label className="text-gray-200 text-base">Folder Access Control</Label>
              <div className="border border-gray-700 rounded-lg overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow className="border-gray-800 hover:bg-gray-800/50">
                      <TableHead className="text-gray-300">Folder</TableHead>
                      <TableHead className="text-center text-gray-300">Read</TableHead>
                      <TableHead className="text-center text-gray-300">Write</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {allFolders.map((folder) => {
                      const perm = getPermission(folder.path);
                      return (
                        <TableRow key={folder.path} className="border-gray-800">
                          <TableCell className="text-white">
                            <div className="flex items-center gap-2">
                              <FolderOpen className="h-4 w-4 text-orange-400" />
                              {folder.name}
                              <span className="text-xs text-gray-500">{folder.path}</span>
                            </div>
                          </TableCell>
                          <TableCell className="text-center">
                            <button
                              type="button"
                              onClick={() => handlePermissionCycle(folder.path, 'read')}
                              className="inline-flex items-center justify-center w-20 h-8 rounded border border-gray-700 hover:border-gray-500 transition-colors bg-gray-800"
                            >
                              <PermStateBadge value={perm?.read ?? null} />
                            </button>
                          </TableCell>
                          <TableCell className="text-center">
                            <button
                              type="button"
                              onClick={() => handlePermissionCycle(folder.path, 'write')}
                              className="inline-flex items-center justify-center w-20 h-8 rounded border border-gray-700 hover:border-gray-500 transition-colors bg-gray-800"
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

            <div className="mt-4 p-3 bg-gray-800 rounded-lg">
              <div className="text-sm text-gray-400">
                <strong className="text-gray-300">Permission States:</strong>
                <ul className="mt-2 space-y-1 ml-4">
                  <li className="flex items-center gap-2">
                    <CheckCircle className="h-3 w-3 text-green-400" />
                    <span><strong className="text-green-400">Allow</strong> — Explicitly grants access (overrides group/domain)</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <XCircle className="h-3 w-3 text-red-400" />
                    <span><strong className="text-red-400">Deny</strong> — Explicitly denies access (overrides group/domain)</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <MinusCircle className="h-3 w-3 text-gray-500" />
                    <span><strong className="text-gray-400">No Action</strong> — Inherits from group or domain permissions</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button 
              variant="outline" 
              onClick={() => setShowEditDialog(false)}
              className="bg-gray-800 border-gray-700 text-white hover:bg-gray-700"
            >
              Cancel
            </Button>
            <Button onClick={handleSave}>
              Save Permissions
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Effective Permissions Dialog */}
      <Dialog open={showEffectiveDialog} onOpenChange={setShowEffectiveDialog}>
        <DialogContent className="bg-gray-900 border-gray-800 text-white max-w-4xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-white">
              Effective Permissions
            </DialogTitle>
            <DialogDescription className="text-gray-400">
              Resolved permissions for <strong>{effectiveUser && getUserIdentifier(effectiveUser)}</strong> across all layers (domain → group → user)
            </DialogDescription>
          </DialogHeader>

          <div className="py-4">
            {Object.keys(effectivePerms).length === 0 ? (
              <Alert className="bg-green-950 border-green-900">
                <Info className="h-4 w-4 text-green-400" />
                <AlertDescription className="text-green-300">
                  No permission rules configured. This user has full access to all folders by default.
                </AlertDescription>
              </Alert>
            ) : (
              <div className="border border-gray-800 rounded-lg overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow className="border-gray-800">
                      <TableHead className="text-gray-300">Path</TableHead>
                      <TableHead className="text-gray-300 text-center">Domain</TableHead>
                      <TableHead className="text-gray-300 text-center">Group</TableHead>
                      <TableHead className="text-gray-300 text-center">User</TableHead>
                      <TableHead className="text-gray-300 text-center">Effective</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {Object.entries(effectivePerms)
                      .sort(([a], [b]) => a.localeCompare(b))
                      .map(([path, entry]) => (
                        <TableRow key={path} className="border-gray-800">
                          <TableCell className="text-white font-mono text-sm">
                            <div className="flex items-center gap-2">
                              <FolderOpen className="h-4 w-4 text-gray-400" />
                              {path}
                            </div>
                          </TableCell>
                          <TableCell className="text-center">
                            {entry.domain ? (
                              <div className="flex justify-center gap-1">
                                <Badge variant="outline" className={entry.domain.canRead ? 'text-blue-300 border-blue-800' : 'text-gray-500 border-gray-700'}>
                                  R
                                </Badge>
                                <Badge variant="outline" className={entry.domain.canWrite ? 'text-blue-300 border-blue-800' : 'text-gray-500 border-gray-700'}>
                                  W
                                </Badge>
                              </div>
                            ) : (
                              <span className="text-gray-600">—</span>
                            )}
                          </TableCell>
                          <TableCell className="text-center">
                            {entry.groupMerged ? (
                              <div>
                                <div className="flex justify-center gap-1">
                                  <Badge variant="outline" className={entry.groupMerged.canRead ? 'text-purple-300 border-purple-800' : 'text-gray-500 border-gray-700'}>
                                    R
                                  </Badge>
                                  <Badge variant="outline" className={entry.groupMerged.canWrite ? 'text-purple-300 border-purple-800' : 'text-gray-500 border-gray-700'}>
                                    W
                                  </Badge>
                                </div>
                                <div className="text-[10px] text-gray-500 mt-1">
                                  {entry.groups.map((g) => g.groupName).join(', ')}
                                </div>
                              </div>
                            ) : (
                              <span className="text-gray-600">—</span>
                            )}
                          </TableCell>
                          <TableCell className="text-center">
                            {entry.user ? (
                              <div className="flex justify-center gap-1">
                                <Badge variant="outline" className={entry.user.canRead ? 'text-orange-300 border-orange-800' : 'text-gray-500 border-gray-700'}>
                                  R
                                </Badge>
                                <Badge variant="outline" className={entry.user.canWrite ? 'text-orange-300 border-orange-800' : 'text-gray-500 border-gray-700'}>
                                  W
                                </Badge>
                              </div>
                            ) : (
                              <span className="text-gray-600">—</span>
                            )}
                          </TableCell>
                          <TableCell className="text-center">
                            <div className="flex justify-center gap-1">
                              <Badge className={entry.effective.canRead ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'}>
                                R
                              </Badge>
                              <Badge className={entry.effective.canWrite ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'}>
                                W
                              </Badge>
                            </div>
                            <div className="text-[10px] text-gray-400 mt-1">
                              via {entry.effective.source}
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </Table>
              </div>
            )}

            <div className="mt-4 flex gap-4 text-xs text-gray-500">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500 inline-block" /> Domain</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-purple-500 inline-block" /> Group (most-permissive across groups)</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-orange-500 inline-block" /> User (highest priority)</span>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
