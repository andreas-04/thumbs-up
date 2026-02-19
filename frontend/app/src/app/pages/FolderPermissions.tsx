import React, { useState } from 'react';
import { useData, User, FolderPermission } from '../contexts/DataContext';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import { Label } from '../components/ui/label';
import { 
  FolderOpen, 
  Shield, 
  Edit, 
  Info,
  CheckCircle,
  XCircle,
  Mail,
  User as UserIcon,
} from 'lucide-react';
import { toast } from 'sonner';

export default function FolderPermissions() {
  const { settings, users, files, updateUser } = useData();
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [permissions, setPermissions] = useState<FolderPermission[]>([]);

  // Get unique folders from files
  const folders = files.filter((f) => f.type === 'folder');

  const openEditDialog = (user: User) => {
    setSelectedUser(user);
    setPermissions([...user.folderPermissions]);
    setShowEditDialog(true);
  };

  const handlePermissionToggle = (folderPath: string, permType: 'read' | 'write') => {
    setPermissions((prev) => {
      const existing = prev.find((p) => p.path === folderPath);
      
      if (existing) {
        // Update existing permission
        return prev.map((p) =>
          p.path === folderPath
            ? { ...p, [permType]: !p[permType] }
            : p
        );
      } else {
        // Add new permission
        return [
          ...prev,
          {
            path: folderPath,
            read: permType === 'read',
            write: permType === 'write',
          },
        ];
      }
    });
  };

  const getPermission = (folderPath: string): FolderPermission | null => {
    return permissions.find((p) => p.path === folderPath) || null;
  };

  const handleSave = () => {
    if (!selectedUser) return;
    
    // Filter out permissions where both read and write are false
    const cleanedPermissions = permissions.filter((p) => p.read || p.write);
    
    updateUser(selectedUser.id, { folderPermissions: cleanedPermissions });
    toast.success('Folder permissions updated successfully');
    setShowEditDialog(false);
    setSelectedUser(null);
    setPermissions([]);
  };

  const getUserIdentifier = (user: User): string => {
    if (settings.authMethod === 'username+password') {
      return user.username || 'N/A';
    }
    return user.email || 'N/A';
  };

  const getPermissionSummary = (user: User): string => {
    if (user.folderPermissions.length === 0) {
      return 'Full access (default)';
    }
    
    const readCount = user.folderPermissions.filter((p) => p.read).length;
    const writeCount = user.folderPermissions.filter((p) => p.write).length;
    
    return `${user.folderPermissions.length} folders - ${readCount} read, ${writeCount} write`;
  };

  if (settings.mode === 'open') {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-semibold text-white">Folder Permissions</h1>
          <p className="text-gray-400 mt-1">
            Configure per-user folder access control
          </p>
        </div>

        <Alert className="bg-yellow-950 border-yellow-900">
          <Shield className="h-4 w-4 text-yellow-400" />
          <AlertDescription className="text-yellow-300">
            Folder permissions are only available in <strong>Protected Mode</strong>.
            Currently, the system is in <strong>Open Mode</strong> - all users have full access to all folders.
            <br />
            <br />
            Switch to Protected Mode in <a href="/admin/settings" className="underline">System Settings</a> to enable folder permissions.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

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
          <strong>Access Control Lists (ACL):</strong> Configure read/write permissions for each user per folder.
          Users without specific permissions will have full access to all folders by default.
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
                          <Badge variant="outline" className="text-green-400 border-green-700">
                            Full Access
                          </Badge>
                        ) : (
                          user.folderPermissions.slice(0, 2).map((perm) => (
                            <Badge key={perm.path} variant="outline" className="text-gray-300 border-gray-700">
                              {perm.path}: {perm.read && 'R'}{perm.write && 'W'}
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
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openEditDialog(user)}
                        className="text-blue-400 hover:text-blue-300"
                      >
                        <Edit className="h-4 w-4 mr-1" />
                        Edit
                      </Button>
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
              Edit Folder Permissions
            </DialogTitle>
            <DialogDescription className="text-gray-400">
              Configure read/write access for <strong>{selectedUser && getUserIdentifier(selectedUser)}</strong>
            </DialogDescription>
          </DialogHeader>
          
          <div className="py-4">
            <Alert className="bg-gray-800 border-gray-700 mb-4">
              <Info className="h-4 w-4 text-gray-400" />
              <AlertDescription className="text-gray-300 text-sm">
                <strong>Default behavior:</strong> If no permissions are set for a folder, the user has full read/write access.
                Set specific permissions to restrict access.
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
                    {folders.map((folder) => {
                      const perm = getPermission(folder.path);
                      return (
                        <TableRow key={folder.id} className="border-gray-800">
                          <TableCell className="text-white">
                            <div className="flex items-center gap-2">
                              <FolderOpen className="h-4 w-4 text-orange-400" />
                              {folder.name}
                              <span className="text-xs text-gray-500">{folder.path}</span>
                            </div>
                          </TableCell>
                          <TableCell className="text-center">
                            <div className="flex justify-center">
                              <Switch
                                checked={perm?.read ?? true}
                                onCheckedChange={() => handlePermissionToggle(folder.path, 'read')}
                              />
                            </div>
                          </TableCell>
                          <TableCell className="text-center">
                            <div className="flex justify-center">
                              <Switch
                                checked={perm?.write ?? true}
                                onCheckedChange={() => handlePermissionToggle(folder.path, 'write')}
                              />
                            </div>
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
                <strong className="text-gray-300">Permission Summary:</strong>
                <ul className="mt-2 space-y-1 ml-4">
                  <li className="flex items-center gap-2">
                    <CheckCircle className="h-3 w-3 text-green-400" />
                    <span>Read: View and download files</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle className="h-3 w-3 text-blue-400" />
                    <span>Write: Upload, modify, and delete files</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <XCircle className="h-3 w-3 text-red-400" />
                    <span>Disabled: No access to folder</span>
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
    </div>
  );
}
