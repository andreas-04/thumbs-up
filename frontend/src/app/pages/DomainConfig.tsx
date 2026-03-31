import React, { useState, useEffect } from 'react';
import { useData, DomainConfig } from '../contexts/DataContext';
import { api } from '../../services/api';
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
import {
  Globe,
  Plus,
  Edit,
  Trash2,
  Info,
  FolderOpen,
} from 'lucide-react';
import { toast } from 'sonner';

interface PermissionRow {
  path: string;
  read: boolean;
  write: boolean;
}

export default function DomainConfigPage() {
  const { domains, refreshDomains } = useData();
  const [showDialog, setShowDialog] = useState(false);
  const [editingDomain, setEditingDomain] = useState<DomainConfig | null>(null);
  const [domainName, setDomainName] = useState('');
  const [permissions, setPermissions] = useState<PermissionRow[]>([]);
  const [allFolders, setAllFolders] = useState<Array<{ path: string; name: string }>>([]);

  useEffect(() => {
    refreshDomains().catch((err) => console.error('Failed to refresh domains:', err));
    api.listFolders()
      .then(({ folders }) => setAllFolders(folders))
      .catch((err) => console.error('Failed to load folders:', err));
  }, [refreshDomains]);

  const openCreateDialog = () => {
    setEditingDomain(null);
    setDomainName('');
    setPermissions([]);
    setShowDialog(true);
  };

  const openEditDialog = (domain: DomainConfig) => {
    setEditingDomain(domain);
    setDomainName(domain.domain);
    setPermissions(
      domain.permissions.map((p) => ({ path: p.path, read: p.read, write: p.write }))
    );
    setShowDialog(true);
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

  const getPermission = (folderPath: string): PermissionRow | undefined => {
    return permissions.find((p) => p.path === folderPath);
  };

  const handleSave = async () => {
    if (!domainName.trim()) {
      toast.error('Domain name is required');
      return;
    }

    const cleanedPermissions = permissions.filter((p) => p.read || p.write);

    try {
      if (editingDomain) {
        await api.updateDomain(editingDomain.id, {
          domain: domainName.trim().toLowerCase(),
          permissions: cleanedPermissions,
        });
        toast.success('Domain config updated');
      } else {
        await api.createDomain({
          domain: domainName.trim().toLowerCase(),
          permissions: cleanedPermissions,
        });
        toast.success('Domain config created');
      }
      await refreshDomains();
      setShowDialog(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save domain config');
    }
  };

  const handleDelete = async (domain: DomainConfig) => {
    try {
      await api.deleteDomain(domain.id);
      toast.success(`Domain "${domain.domain}" deleted`);
      await refreshDomains();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete domain');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-white">Domain Configuration</h1>
          <p className="text-gray-400 mt-1">
            Set default permissions for users by email domain
          </p>
        </div>
        <Button onClick={openCreateDialog} className="gap-2">
          <Plus className="h-4 w-4" />
          Add Domain
        </Button>
      </div>

      <Alert className="bg-blue-950 border-blue-900">
        <Info className="h-4 w-4 text-blue-400" />
        <AlertDescription className="text-blue-300">
          Domains listed here are automatically allowlisted for user signup. Users from these
          domains get the default permissions defined below. Group and user-level overrides
          take precedence over domain defaults.
        </AlertDescription>
      </Alert>

      <Card className="bg-gray-900 border-gray-800">
        <CardHeader>
          <CardTitle className="text-white">Configured Domains</CardTitle>
          <CardDescription className="text-gray-400">
            Click "Edit" to manage default permissions for a domain
          </CardDescription>
        </CardHeader>
        <CardContent>
          {domains.length === 0 ? (
            <p className="text-gray-500 text-center py-8">
              No domains configured yet. Click "Add Domain" to get started.
            </p>
          ) : (
            <div className="border border-gray-800 rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="border-gray-800 hover:bg-gray-800/50">
                    <TableHead className="text-gray-300">Domain</TableHead>
                    <TableHead className="text-gray-300">Permissions</TableHead>
                    <TableHead className="text-right text-gray-300">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {domains.map((domain) => (
                    <TableRow key={domain.id} className="border-gray-800 hover:bg-gray-800/50">
                      <TableCell className="font-medium text-white">
                        <div className="flex items-center gap-2">
                          <Globe className="h-4 w-4 text-blue-400" />
                          {domain.domain}
                        </div>
                      </TableCell>
                      <TableCell className="text-gray-400">
                        <div className="flex flex-wrap gap-1">
                          {domain.permissions.length === 0 ? (
                            <Badge variant="outline" className="text-gray-500 border-gray-700">
                              No permissions
                            </Badge>
                          ) : (
                            domain.permissions.slice(0, 3).map((perm) => (
                              <Badge
                                key={perm.path}
                                variant="outline"
                                className="text-blue-300 border-blue-800"
                              >
                                {perm.path} {perm.read ? 'r' : ''}{perm.write ? 'w' : ''}
                              </Badge>
                            ))
                          )}
                          {domain.permissions.length > 3 && (
                            <Badge variant="outline" className="text-gray-400 border-gray-700">
                              +{domain.permissions.length - 3} more
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditDialog(domain)}
                            className="text-gray-400 hover:text-white"
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(domain)}
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

      {/* Create / Edit Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="bg-gray-900 border-gray-800 max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-white">
              {editingDomain ? 'Edit Domain Config' : 'Add Domain Config'}
            </DialogTitle>
            <DialogDescription className="text-gray-400">
              Set the domain name and default folder permissions for users from this domain.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 py-4">
            <div className="space-y-2">
              <Label className="text-gray-300">Domain Name</Label>
              <Input
                value={domainName}
                onChange={(e) => setDomainName(e.target.value)}
                placeholder="e.g. company.com"
                className="bg-gray-800 border-gray-700 text-white"
              />
            </div>

            <div className="space-y-3">
              <Label className="text-gray-300">Default Folder Permissions</Label>
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
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDialog(false)} className="border-gray-700 text-gray-300">
              Cancel
            </Button>
            <Button onClick={handleSave}>
              {editingDomain ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
