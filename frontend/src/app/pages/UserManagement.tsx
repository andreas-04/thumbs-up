import React, { useState } from 'react';
import { useData, User } from '../contexts/DataContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
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
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <div>
          <h1 className="text-lg font-medium text-foreground">users</h1>
          <p className="text-muted-foreground text-xs mt-0.5">
            manage approved users
          </p>
        </div>
        <Button onClick={() => setShowAddDialog(true)} className="h-8 text-xs">
          <Plus className="h-3.5 w-3.5 mr-1.5" />
          invite
        </Button>
      </div>

      <Card className="glass">
        <CardHeader className="pb-3">
          <div className="pt-1">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 transform -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                placeholder="filter..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 glass border-glass-border text-foreground placeholder:text-term-dim h-8 text-xs"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="border border-glass-border rounded overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="border-glass-border hover:bg-glass-highlight">
                  <TableHead className="text-muted-foreground text-xs">email</TableHead>
                  <TableHead className="text-muted-foreground text-xs">cert</TableHead>
                  <TableHead className="text-muted-foreground text-xs">status</TableHead>
                  <TableHead className="text-muted-foreground text-xs hidden sm:table-cell">added</TableHead>
                  <TableHead className="text-right text-muted-foreground text-xs">actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredUsers.length === 0 ? (
                  <TableRow className="border-glass-border">
                    <TableCell colSpan={5} className="text-center py-6 text-muted-foreground text-xs">
                      {searchQuery ? 'no matches' : 'no users -- approve an email to start'}
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredUsers.map((user) => (
                    <TableRow key={user.id} className="border-glass-border hover:bg-glass-highlight">
                      <TableCell className="text-foreground text-xs">
                        <div className="flex items-center gap-1.5">
                          <Mail className="h-3 w-3 text-muted-foreground" />
                          {getUserIdentifier(user)}
                        </div>
                      </TableCell>
                      <TableCell>
                        {user.certRevoked ? (
                          <span className="text-term-yellow text-xs">revoked</span>
                        ) : (
                          <span className="text-term-green text-xs">active</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <span className={`text-xs ${user.last_login ? 'text-foreground' : 'text-muted-foreground'}`}>
                          {user.last_login ? 'registered' : 'invited'}
                        </span>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-xs hidden sm:table-cell">
                        {new Date(user.createdAt).toLocaleDateString()}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-0.5">
                          {!user.certRevoked ? (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => { setSelectedUser(user); setShowRevokeDialog(true); }}
                              className="text-term-yellow hover:text-term-yellow/80 h-7 w-7"
                              title="Revoke Certificate"
                            >
                              <ShieldOff className="h-3.5 w-3.5" />
                            </Button>
                          ) : (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => { setSelectedUser(user); setShowReissueDialog(true); }}
                              className="text-term-blue hover:text-term-blue/80 h-7 w-7"
                              title="Re-issue Certificate"
                            >
                              <RefreshCw className="h-3.5 w-3.5" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => openDeleteDialog(user)}
                            className="text-term-red/70 hover:text-term-red h-7 w-7"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
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
        <DialogContent className="glass border-glass-border text-foreground">
          <DialogHeader>
            <DialogTitle className="text-foreground text-sm">approve email</DialogTitle>
            <DialogDescription className="text-muted-foreground text-xs">
              user will receive a client certificate for secure access
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-3">
            <div className="space-y-1">
              <Label htmlFor="add-email" className="text-muted-foreground text-xs">email</Label>
              <Input
                id="add-email"
                type="email"
                placeholder="user@example.com"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="glass border-glass-border text-foreground placeholder:text-term-dim h-8 text-xs"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddDialog(false)} className="glass border-glass-border text-foreground hover:bg-glass-highlight h-8 text-xs">
              cancel
            </Button>
            <Button onClick={handleAdd} className="h-8 text-xs">approve</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent className="glass border-glass-border">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-foreground text-sm">remove user?</AlertDialogTitle>
            <AlertDialogDescription className="text-muted-foreground text-xs">
              remove <strong className="text-foreground">{selectedUser && getUserIdentifier(selectedUser)}</strong> -- they will lose file access
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="glass border-glass-border text-foreground hover:bg-glass-highlight h-8 text-xs">cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-term-red/20 text-term-red border border-term-red/30 hover:bg-term-red/30 h-8 text-xs">
              remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Revoke Certificate Dialog */}
      <AlertDialog open={showRevokeDialog} onOpenChange={setShowRevokeDialog}>
        <AlertDialogContent className="glass border-glass-border">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-foreground text-sm">revoke certificate?</AlertDialogTitle>
            <AlertDialogDescription className="text-muted-foreground text-xs">
              revoke cert for <strong className="text-foreground">{selectedUser && getUserIdentifier(selectedUser)}</strong> -- immediate loss of file access
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="glass border-glass-border text-foreground hover:bg-glass-highlight h-8 text-xs">cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleRevoke} className="bg-term-yellow/20 text-term-yellow border border-term-yellow/30 hover:bg-term-yellow/30 h-8 text-xs">
              revoke
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Re-issue Certificate Dialog */}
      <AlertDialog open={showReissueDialog} onOpenChange={setShowReissueDialog}>
        <AlertDialogContent className="glass border-glass-border">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-foreground text-sm">re-issue certificate?</AlertDialogTitle>
            <AlertDialogDescription className="text-muted-foreground text-xs">
              new cert will be generated and emailed to <strong className="text-foreground">{selectedUser && getUserIdentifier(selectedUser)}</strong>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="glass border-glass-border text-foreground hover:bg-glass-highlight h-8 text-xs">cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleReissue} className="bg-term-blue/20 text-term-blue border border-term-blue/30 hover:bg-term-blue/30 h-8 text-xs">
              re-issue
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
