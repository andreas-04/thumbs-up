import React, { useState } from 'react';
import { useData, User } from '../contexts/DataContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../components/ui/alert-dialog';
import { Badge } from '../components/ui/badge';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Plus, Trash2, Search, Mail, Key, ShieldOff, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../../services/api';

export default function UserManagement() {
  const { settings, users, addUser, deleteUser, refreshUsers } = useData();
  const [searchQuery, setSearchQuery] = useState('');
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [showRevokeDialog, setShowRevokeDialog] = useState(false);
  const [showReissueDialog, setShowReissueDialog] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);

  // Refresh users whenever this page is visited
  React.useEffect(() => {
    refreshUsers().catch((err) => console.error('Failed to refresh users:', err));
  }, [refreshUsers]);

  // Form state
  const [formData, setFormData] = useState({
    email: '',
  });

  const filteredUsers = users.filter((user) => {
    const searchLower = searchQuery.toLowerCase();
    return (
      user.email?.toLowerCase().includes(searchLower) ||
      user.username?.toLowerCase().includes(searchLower)
    );
  });

  const openDeleteDialog = (user: User) => {
    setSelectedUser(user);
    setShowDeleteDialog(true);
  };

  const resetForm = () => {
    setFormData({ email: '' });
  };

  const validateForm = (): boolean => {
    if (!formData.email || !formData.email.includes('@')) {
      toast.error('Please enter a valid email address');
      return false;
    }
    return true;
  };

  const handleAdd = async () => {
    if (!validateForm()) return;

    try {
      const result = await addUser({ email: formData.email });
      if (result?.approved) {
        toast.success('User approved for protected file access');
      } else {
        toast.success('Email approved successfully');
      }
      setShowAddDialog(false);
      resetForm();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to approve email');
    }
  };

  const handleDelete = async () => {
    if (!selectedUser) return;
    try {
      await deleteUser(selectedUser.id);
      toast.success('User removed successfully');
      setShowDeleteDialog(false);
      setSelectedUser(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to remove user');
    }
  };

  const handleRevoke = async () => {
    if (!selectedUser) return;
    try {
      await api.revokeCert(selectedUser.id);
      toast.success('Certificate revoked successfully');
      setShowRevokeDialog(false);
      setSelectedUser(null);
      await refreshUsers();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to revoke certificate');
    }
  };

  const handleReissue = async () => {
    if (!selectedUser) return;
    try {
      await api.reissueCert(selectedUser.id);
      toast.success('New certificate issued and emailed to user');
      setShowReissueDialog(false);
      setSelectedUser(null);
      await refreshUsers();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to re-issue certificate');
    }
  };

  const getUserIdentifier = (user: User): string => {
    return user.email || 'N/A';
  };

  if (!settings) {
    return null;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-white">User Management</h1>
          <p className="text-gray-400 mt-1">
            Manage approved users for file access
          </p>
        </div>
        <Button onClick={() => setShowAddDialog(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Approve Email
        </Button>
      </div>

      <Alert className="bg-blue-950 border-blue-900">
        <Key className="h-4 w-4 text-blue-400" />
        <AlertDescription className="text-blue-300">
          <strong>How it works:</strong> Invite users by entering their email. They'll receive a client certificate for secure access.
          Users with an allowed email domain can also self-register in System Settings.
        </AlertDescription>
      </Alert>

      <Card className="bg-gray-900 border-gray-800">
        <CardHeader>
          <CardTitle className="text-white">Users</CardTitle>
          <CardDescription className="text-gray-400">
            Invited users can access protected files. Configure domain allowlists in System Settings.
          </CardDescription>
          <div className="pt-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                placeholder="Search by email..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="border border-gray-800 rounded-lg overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="border-gray-800 hover:bg-gray-800/50">
                  <TableHead className="text-gray-300">Email</TableHead>
                  <TableHead className="text-gray-300">Access</TableHead>
                  <TableHead className="text-gray-300">Certificate</TableHead>
                  <TableHead className="text-gray-300">Status</TableHead>
                  <TableHead className="text-gray-300">Added</TableHead>
                  <TableHead className="text-gray-300">Permissions</TableHead>
                  <TableHead className="text-right text-gray-300">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredUsers.length === 0 ? (
                  <TableRow className="border-gray-800">
                    <TableCell colSpan={7} className="text-center py-8 text-gray-500">
                      {searchQuery ? 'No users found matching your search' : 'No users yet. Approve an email to grant protected file access.'}
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredUsers.map((user) => (
                    <TableRow key={user.id} className="border-gray-800 hover:bg-gray-800/50">
                      <TableCell className="font-medium text-white">
                        <div className="flex items-center gap-2">
                          <Mail className="h-4 w-4 text-gray-400" />
                          {getUserIdentifier(user)}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="default" className="bg-green-700 text-green-100">
                          Protected
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {user.certRevoked ? (
                          <Badge variant="default" className="bg-amber-700 text-amber-100">
                            Revoked
                          </Badge>
                        ) : (
                          <Badge variant="default" className="bg-green-700 text-green-100">
                            Active
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant={user.last_login ? 'default' : 'secondary'}>
                          {user.last_login ? 'Registered' : 'Invited'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-gray-400">
                        {new Date(user.createdAt).toLocaleDateString()}
                      </TableCell>
                      <TableCell className="text-gray-400">
                        {user.folderPermissions.length > 0 ? (
                          <Badge variant="outline" className="text-gray-300 border-gray-700">
                            {user.folderPermissions.length} folder(s)
                          </Badge>
                        ) : (
                          <span className="text-sm text-gray-500">Default</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          {!user.certRevoked ? (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => { setSelectedUser(user); setShowRevokeDialog(true); }}
                              className="text-amber-400 hover:text-amber-300"
                              title="Revoke Certificate"
                            >
                              <ShieldOff className="h-4 w-4" />
                            </Button>
                          ) : (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => { setSelectedUser(user); setShowReissueDialog(true); }}
                              className="text-blue-400 hover:text-blue-300"
                              title="Re-issue Certificate"
                            >
                              <RefreshCw className="h-4 w-4" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => openDeleteDialog(user)}
                            className="text-red-400 hover:text-red-300"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Add User Dialog */}
      <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
        <DialogContent className="bg-gray-900 border-gray-800 text-white">
          <DialogHeader>
            <DialogTitle className="text-white">Approve Email</DialogTitle>
            <DialogDescription className="text-gray-400">
              Add an email address to the approved list. The user can then create their own account using this email.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="add-email" className="text-gray-200">Email Address *</Label>
              <Input
                id="add-email"
                type="email"
                placeholder="user@example.com"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddDialog(false)} className="bg-gray-800 border-gray-700 text-white hover:bg-gray-700">
              Cancel
            </Button>
            <Button onClick={handleAdd}>Approve Email</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent className="bg-gray-900 border-gray-800">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-white">Remove Email?</AlertDialogTitle>
            <AlertDialogDescription className="text-gray-400">
              Are you sure you want to remove <strong>{selectedUser && getUserIdentifier(selectedUser)}</strong> from the approved list?
              They will no longer be able to access files on this device.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="bg-gray-800 border-gray-700 text-white hover:bg-gray-700">Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-red-600 hover:bg-red-700">
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Revoke Certificate Dialog */}
      <AlertDialog open={showRevokeDialog} onOpenChange={setShowRevokeDialog}>
        <AlertDialogContent className="bg-gray-900 border-gray-800">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-white">Revoke Certificate?</AlertDialogTitle>
            <AlertDialogDescription className="text-gray-400">
              This will revoke the client certificate for <strong>{selectedUser && getUserIdentifier(selectedUser)}</strong>.
              They will lose access to protected files immediately.
              Their account and permissions will be preserved.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="bg-gray-800 border-gray-700 text-white hover:bg-gray-700">Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleRevoke} className="bg-amber-600 hover:bg-amber-700">
              Revoke Certificate
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Re-issue Certificate Dialog */}
      <AlertDialog open={showReissueDialog} onOpenChange={setShowReissueDialog}>
        <AlertDialogContent className="bg-gray-900 border-gray-800">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-white">Re-issue Certificate?</AlertDialogTitle>
            <AlertDialogDescription className="text-gray-400">
              A new client certificate will be generated and emailed to <strong>{selectedUser && getUserIdentifier(selectedUser)}</strong>.
              They will need to install the new certificate to regain file access.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="bg-gray-800 border-gray-700 text-white hover:bg-gray-700">Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleReissue} className="bg-blue-600 hover:bg-blue-700">
              Re-issue Certificate
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
