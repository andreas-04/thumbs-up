import React, { useState, useEffect } from 'react';
import { useData, DomainConfig } from '../contexts/DataContext';
import { api } from '../../services/api';
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
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg text-foreground">domain configuration</h1>
          <p className="text-muted-foreground text-xs mt-1">
            default permissions by email domain
          </p>
        </div>
        <Button onClick={openCreateDialog} size="sm" className="gap-1.5 h-7 text-xs">
          <Plus className="h-3.5 w-3.5" />
          add domain
        </Button>
      </div>

      <Alert className="glass border-glass-border">
        <Info className="h-3.5 w-3.5 text-term-blue" />
        <AlertDescription className="text-muted-foreground text-xs">
          domains listed here are auto-allowlisted for signup. group and user-level overrides take precedence.
        </AlertDescription>
      </Alert>

      <Card className="glass">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm text-foreground">configured domains</CardTitle>
        </CardHeader>
        <CardContent>
          {domains.length === 0 ? (
            <p className="text-muted-foreground text-center py-6 text-xs">
              no domains configured yet.
            </p>
          ) : (
            <div className="border border-glass-border rounded overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="border-glass-border hover:bg-glass-highlight">
                    <TableHead className="text-muted-foreground text-xs">domain</TableHead>
                    <TableHead className="text-muted-foreground text-xs hidden sm:table-cell">permissions</TableHead>
                    <TableHead className="text-right text-muted-foreground text-xs"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {domains.map((domain) => (
                    <TableRow key={domain.id} className="border-glass-border hover:bg-glass-highlight">
                      <TableCell className="text-foreground text-xs">
                        <div className="flex items-center gap-1.5">
                          <Globe className="h-3.5 w-3.5 text-term-blue" />
                          {domain.domain}
                        </div>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-xs hidden sm:table-cell">
                        {domain.permissions.length === 0 ? (
                          <span className="text-term-dim">none</span>
                        ) : (
                          <span>
                            {domain.permissions.slice(0, 3).map((perm) => (
                              <span key={perm.path} className="mr-2 text-term-blue">
                                {perm.path} {perm.read ? 'r' : ''}{perm.write ? 'w' : ''}
                              </span>
                            ))}
                            {domain.permissions.length > 3 && (
                              <span className="text-term-dim">+{domain.permissions.length - 3}</span>
                            )}
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditDialog(domain)}
                            className="text-muted-foreground hover:text-foreground h-7 w-7 p-0"
                          >
                            <Edit className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(domain)}
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

      {/* Create / Edit Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="glass border-glass-border max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-foreground text-sm">
              {editingDomain ? 'edit domain' : 'add domain'}
            </DialogTitle>
            <DialogDescription className="text-muted-foreground text-xs">
              set domain name and default folder permissions.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-3">
            <div className="space-y-1">
              <Label className="text-muted-foreground text-xs">domain name</Label>
              <Input
                value={domainName}
                onChange={(e) => setDomainName(e.target.value)}
                placeholder="company.com"
                className="glass border-glass-border text-foreground h-8 text-xs"
              />
            </div>

            <div className="space-y-1">
              <Label className="text-muted-foreground text-xs">folder permissions</Label>
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
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDialog(false)} className="glass border-glass-border text-foreground h-8 text-xs">
              cancel
            </Button>
            <Button onClick={handleSave} className="h-8 text-xs">
              {editingDomain ? 'update' : 'create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
