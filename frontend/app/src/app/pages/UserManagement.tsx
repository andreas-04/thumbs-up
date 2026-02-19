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
import { Plus, Pencil, Trash2, Search, Shield, Mail, Key } from 'lucide-react';
import { toast } from 'sonner';

export default function UserManagement() {
  const { settings, users, addUser, updateUser, deleteUser } = useData();
  const [searchQuery, setSearchQuery] = useState('');
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);

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

  const openEditDialog = (user: User) => {
    setSelectedUser(user);
    setFormData({
      email: user.email || '',
    });
    setShowEditDialog(true);
  };

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

  const handleAdd = () => {
    if (!validateForm()) return;

    // Check for duplicates
    const isDuplicate = users.some((u) => u.email === formData.email);

    if (isDuplicate) {
      toast.error('This email is already approved');
      return;
    }

    addUser({ email: formData.email });
    toast.success('Email approved successfully');
    setShowAddDialog(false);
    resetForm();
  };

  const handleEdit = () => {
    if (!selectedUser || !validateForm()) return;

    updateUser(selectedUser.id, { email: formData.email });
    toast.success('Email updated successfully');
    setShowEditDialog(false);
    setSelectedUser(null);
    resetForm();
  };

  const handleDelete = () => {
    if (!selectedUser) return;
    deleteUser(selectedUser.id);
    toast.success('User removed successfully');
    setShowDeleteDialog(false);
    setSelectedUser(null);
  };

  const getUserIdentifier = (user: User): string => {
    return user.email || 'N/A';
  };

  if (settings.mode === 'open') {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-semibold text-white">User Management</h1>
          <p className="text-gray-400 mt-1">
            Manage approved users for file access
          </p>
        </div>

        <Alert className="bg-yellow-950 border-yellow-900">
          <Shield className="h-4 w-4 text-yellow-400" />
          <AlertDescription className="text-yellow-300">
            User management is only available in <strong>Protected Mode</strong>.
            Currently, the system is in <strong>Open Mode</strong> - all users can access files without approval.
            <br />
            <br />
            Switch to Protected Mode in <a href="/admin/settings" className="underline">System Settings</a> to enable user management.
          </AlertDescription>
        </Alert>
      </div>
    );
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

      {/* Auth Method Info */}
      <Alert className="bg-blue-950 border-blue-900">
        <Key className="h-4 w-4 text-blue-400" />
        <AlertDescription className="text-blue-300">
          <strong>How it works:</strong> Add email addresses to the approved list below. 
          Users with approved emails can then create their own accounts via the signup page.
        </AlertDescription>
      </Alert>

      <Card className="bg-gray-900 border-gray-800">
        <CardHeader>
          <CardTitle className="text-white">Approved Emails</CardTitle>
          <CardDescription className="text-gray-400">
            Users with these emails can create accounts and access files in Protected Mode
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
                  <TableHead className="text-gray-300">Status</TableHead>
                  <TableHead className="text-gray-300">Added</TableHead>
                  <TableHead className="text-gray-300">Permissions</TableHead>
                  <TableHead className="text-right text-gray-300">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredUsers.length === 0 ? (
                  <TableRow className="border-gray-800">
                    <TableCell colSpan={5} className="text-center py-8 text-gray-500">
                      {searchQuery ? 'No users found matching your search' : 'No approved users yet. Add users to grant access.'}
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
                        <Badge variant={user.last_login ? 'default' : 'secondary'}>
                          {user.last_login ? 'Registered' : 'Pending'}
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
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => openEditDialog(user)}
                            className="text-gray-400 hover:text-white"
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
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

      {/* Edit User Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent className="bg-gray-900 border-gray-800 text-white">
          <DialogHeader>
            <DialogTitle className="text-white">Edit User</DialogTitle>
            <DialogDescription className="text-gray-400">
              Update user information
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="edit-email" className="text-gray-200">Email Address *</Label>
              <Input
                id="edit-email"
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditDialog(false)} className="bg-gray-800 border-gray-700 text-white hover:bg-gray-700">
              Cancel
            </Button>
            <Button onClick={handleEdit}>Save Changes</Button>
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
    </div>
  );
}
