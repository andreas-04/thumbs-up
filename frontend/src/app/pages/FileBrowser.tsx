import React, { useState, useRef } from 'react';
import { useData, FileItem } from '../contexts/DataContext';
import { api } from '../../services/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
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
import { Label } from '../components/ui/label';
import {
  FolderOpen,
  File,
  Home,
  ChevronRight,
  Search,
  Download,
  Upload,
  Loader2,
  Trash2,
  Pencil,
  GripVertical,
} from 'lucide-react';
import { toast } from 'sonner';

export default function FileBrowser() {
  const { files, currentPath, refreshFiles, settings } = useData();
  const [searchQuery, setSearchQuery] = useState('');
  const [showNewFolderDialog, setShowNewFolderDialog] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Rename state
  const [showRenameDialog, setShowRenameDialog] = useState(false);
  const [renameTarget, setRenameTarget] = useState<FileItem | null>(null);
  const [renameName, setRenameName] = useState('');

  // Delete state
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<FileItem | null>(null);

  // Drag state
  const [dragItem, setDragItem] = useState<FileItem | null>(null);
  const [dropTarget, setDropTarget] = useState<string | null>(null);

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files;
    if (!selectedFiles || selectedFiles.length === 0) return;

    setUploading(true);
    try {
      const apiPath = currentPath === '/' ? '' : currentPath.replace(/^\/+/, '');
      for (let i = 0; i < selectedFiles.length; i++) {
        await api.uploadFile(selectedFiles[i], apiPath);
      }
      toast.success(
        selectedFiles.length === 1
          ? `Uploaded "${selectedFiles[0].name}"`
          : `Uploaded ${selectedFiles.length} files`
      );
      refreshFiles(currentPath);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleCreateFolder = async () => {
    const name = newFolderName.trim();
    if (!name) {
      toast.error('Folder name is required');
      return;
    }
    try {
      const apiPath = currentPath === '/' ? '' : currentPath.replace(/^\/+/, '');
      await api.createDirectory(apiPath, name);
      toast.success(`Folder "${name}" created`);
      setShowNewFolderDialog(false);
      setNewFolderName('');
      refreshFiles(currentPath);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create folder');
    }
  };

  const handleRename = async () => {
    if (!renameTarget) return;
    const name = renameName.trim();
    if (!name) {
      toast.error('Name is required');
      return;
    }
    try {
      const filePath = renameTarget.path.replace(/^\/+/, '');
      await api.renameFile(filePath, name);
      toast.success(`Renamed to "${name}"`);
      setShowRenameDialog(false);
      setRenameTarget(null);
      refreshFiles(currentPath);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Rename failed');
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      const filePath = deleteTarget.path.replace(/^\/+/, '');
      await api.deleteFile(filePath);
      toast.success(`Deleted "${deleteTarget.name}"`);
      setShowDeleteDialog(false);
      setDeleteTarget(null);
      refreshFiles(currentPath);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Delete failed');
    }
  };

  // Drag-and-drop handlers
  const handleDragStart = (e: React.DragEvent, file: FileItem) => {
    setDragItem(file);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', file.path);
  };

  const handleDragOver = (e: React.DragEvent, folder: FileItem | 'parent') => {
    e.preventDefault();
    e.stopPropagation();
    if (!dragItem) return;
    // Cannot drop onto self
    if (folder !== 'parent' && folder.path === dragItem.path) return;
    e.dataTransfer.dropEffect = 'move';
    const targetPath = folder === 'parent'
      ? (currentPath === '/' ? '/' : '/' + currentPath.split('/').filter(Boolean).slice(0, -1).join('/') || '/')
      : folder.path;
    setDropTarget(targetPath);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setDropTarget(null);
  };

  const handleDrop = async (e: React.DragEvent, folder: FileItem | 'parent') => {
    e.preventDefault();
    e.stopPropagation();
    setDropTarget(null);

    if (!dragItem) return;
    if (folder !== 'parent' && folder.path === dragItem.path) return;

    const destDir = folder === 'parent'
      ? (() => {
          const parts = currentPath.split('/').filter(Boolean);
          parts.pop();
          return parts.join('/');
        })()
      : folder.path.replace(/^\/+/, '');

    try {
      const srcPath = dragItem.path.replace(/^\/+/, '');
      await api.moveFile(srcPath, destDir);
      toast.success(`Moved "${dragItem.name}" to /${destDir || 'root'}`);
      refreshFiles(currentPath);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Move failed');
    }
    setDragItem(null);
  };

  const handleDragEnd = () => {
    setDragItem(null);
    setDropTarget(null);
  };

  if (!settings) return null;

  const filteredFiles = files.filter((f) =>
    f.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const pathParts = currentPath.split('/').filter(Boolean);

  const navigateToFolder = (path: string) => {
    const normalizedPath = path === '/' ? '/' : '/' + path.replace(/^\/+/, '');
    refreshFiles(normalizedPath);
    setSearchQuery('');
  };

  const goBack = () => {
    if (currentPath === '/') return;
    const parts = currentPath.split('/').filter(Boolean);
    parts.pop();
    const parentPath = parts.length === 0 ? '/' : '/' + parts.join('/');
    navigateToFolder(parentPath);
  };

  const formatFileSize = (bytes?: number): string => {
    if (!bytes) return '-';
    const kb = bytes / 1024;
    if (kb < 1024) return `${kb.toFixed(1)} KB`;
    const mb = kb / 1024;
    if (mb < 1024) return `${mb.toFixed(1)} MB`;
    const gb = mb / 1024;
    return `${gb.toFixed(1)} GB`;
  };

  const handleFileClick = (file: FileItem) => {
    if (file.type === 'folder') {
      const newPath = file.path.startsWith('/') ? file.path : '/' + file.path;
      navigateToFolder(newPath);
    } else {
      downloadFile(file.path, file.name);
    }
  };

  const downloadFile = (filePath: string, fileName: string) => {
    const token = localStorage.getItem('auth_token');
    const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
    const url = `${baseUrl}/api/v1/files/download?path=${encodeURIComponent(filePath)}`;
    
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    
    if (token) {
      fetch(url, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
        .then(response => {
          if (!response.ok) throw new Error('Download failed');
          return response.blob();
        })
        .then(blob => {
          const blobUrl = URL.createObjectURL(blob);
          link.href = blobUrl;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          URL.revokeObjectURL(blobUrl);
        })
        .catch(err => console.error('Download error:', err));
    } else {
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  return (
    <div className="space-y-4">
      <Card className="glass">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm text-foreground">files</CardTitle>
          
          {/* Breadcrumb Navigation */}
          <div className="pt-2 flex items-center gap-1 text-xs">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigateToFolder('/')}
              className="text-muted-foreground hover:text-foreground h-6 px-1.5"
            >
              <Home className="h-3.5 w-3.5" />
            </Button>
            {pathParts.map((part, index) => {
              const path = '/' + pathParts.slice(0, index + 1).join('/');
              return (
                <div key={path} className="flex items-center gap-1">
                  <ChevronRight className="h-3 w-3 text-term-dim" />
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => navigateToFolder(path)}
                    className="text-muted-foreground hover:text-foreground h-6 px-1.5 text-xs"
                  >
                    {part}
                  </Button>
                </div>
              );
            })}
          </div>

          {/* Search */}
          <div className="pt-2">
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
          {/* Hidden file input for uploads */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleFileSelected}
          />

          {/* Action Buttons */}
          <div className="flex gap-2 mb-3">
            <Button
              size="sm"
              variant="outline"
              className="glass border-glass-border text-foreground hover:bg-glass-highlight h-7 text-xs"
              onClick={handleUploadClick}
              disabled={uploading}
            >
              {uploading ? (
                <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
              ) : (
                <Upload className="h-3.5 w-3.5 mr-1.5" />
              )}
              {uploading ? 'uploading...' : 'upload'}
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="glass border-glass-border text-foreground hover:bg-glass-highlight h-7 text-xs"
              onClick={() => { setNewFolderName(''); setShowNewFolderDialog(true); }}
            >
              <FolderOpen className="h-3.5 w-3.5 mr-1.5" />
              new folder
            </Button>
          </div>

          <div className="border border-glass-border rounded overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="border-glass-border hover:bg-glass-highlight">
                  <TableHead className="text-muted-foreground text-xs w-6"></TableHead>
                  <TableHead className="text-muted-foreground text-xs">name</TableHead>
                  <TableHead className="text-muted-foreground text-xs hidden sm:table-cell">size</TableHead>
                  <TableHead className="text-muted-foreground text-xs hidden sm:table-cell">modified</TableHead>
                  <TableHead className="text-right text-muted-foreground text-xs w-20"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {/* Back button if not at root */}
                {currentPath !== '/' && (
                  <TableRow 
                    className={`border-glass-border hover:bg-glass-highlight cursor-pointer ${dropTarget === (currentPath === '/' ? '/' : '/' + currentPath.split('/').filter(Boolean).slice(0, -1).join('/') || '/') ? 'bg-term-blue/20' : ''}`}
                    onClick={goBack}
                    onDragOver={(e) => handleDragOver(e, 'parent')}
                    onDragLeave={handleDragLeave}
                    onDrop={(e) => handleDrop(e, 'parent')}
                  >
                    <TableCell className="w-6"></TableCell>
                    <TableCell colSpan={4} className="text-muted-foreground text-xs">
                      <div className="flex items-center gap-1.5">
                        <FolderOpen className="h-3.5 w-3.5" />
                        <span>..</span>
                      </div>
                    </TableCell>
                  </TableRow>
                )}

                {filteredFiles.length === 0 ? (
                  <TableRow className="border-glass-border">
                    <TableCell colSpan={5} className="text-center py-6 text-muted-foreground text-xs">
                      {searchQuery ? 'no matches' : 'empty'}
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredFiles
                    .sort((a, b) => {
                      if (a.type !== b.type) {
                        return a.type === 'folder' ? -1 : 1;
                      }
                      return a.name.localeCompare(b.name);
                    })
                    .map((file) => {
                      const isDropping = file.type === 'folder' && dropTarget === file.path;
                      const isDragging = dragItem?.path === file.path;
                      return (
                        <TableRow 
                          key={file.id || file.path} 
                          className={`border-glass-border hover:bg-glass-highlight cursor-pointer ${isDropping ? 'bg-term-blue/20' : ''} ${isDragging ? 'opacity-40' : ''}`}
                          onClick={() => handleFileClick(file)}
                          draggable
                          onDragStart={(e) => handleDragStart(e, file)}
                          onDragEnd={handleDragEnd}
                          onDragOver={file.type === 'folder' ? (e) => handleDragOver(e, file) : undefined}
                          onDragLeave={file.type === 'folder' ? handleDragLeave : undefined}
                          onDrop={file.type === 'folder' ? (e) => handleDrop(e, file) : undefined}
                        >
                          <TableCell className="w-6 px-1">
                            <GripVertical className="h-3 w-3 text-muted-foreground/50 cursor-grab" />
                          </TableCell>
                          <TableCell className="text-foreground text-xs">
                            <div className="flex items-center gap-1.5">
                              {file.type === 'folder' ? (
                                <FolderOpen className="h-3.5 w-3.5 text-term-yellow" />
                              ) : (
                                <File className="h-3.5 w-3.5 text-term-blue" />
                              )}
                              {file.name}
                            </div>
                          </TableCell>
                          <TableCell className="text-muted-foreground text-xs hidden sm:table-cell">
                            {formatFileSize(file.size)}
                          </TableCell>
                          <TableCell className="text-muted-foreground text-xs hidden sm:table-cell">
                            {new Date(file.modifiedAt).toLocaleDateString()}
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex items-center justify-end gap-0.5">
                              {file.type === 'file' && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    downloadFile(file.path, file.name);
                                  }}
                                  className="text-term-blue hover:text-term-cyan h-7 w-7 p-0"
                                >
                                  <Download className="h-3.5 w-3.5" />
                                </Button>
                              )}
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setRenameTarget(file);
                                  setRenameName(file.name);
                                  setShowRenameDialog(true);
                                }}
                                className="text-muted-foreground hover:text-foreground h-7 w-7 p-0"
                              >
                                <Pencil className="h-3.5 w-3.5" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setDeleteTarget(file);
                                  setShowDeleteDialog(true);
                                }}
                                className="text-destructive hover:text-destructive h-7 w-7 p-0"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    })
                )}
              </TableBody>
            </Table>
          </div>

          {/* File Stats */}
          <div className="mt-3 text-xs text-muted-foreground">
            {filteredFiles.length} item{filteredFiles.length !== 1 ? 's' : ''}
            {dragItem && <span className="ml-2 text-term-blue">drag to a folder to move</span>}
          </div>
        </CardContent>
      </Card>

      {/* New Folder Dialog */}
      <Dialog open={showNewFolderDialog} onOpenChange={setShowNewFolderDialog}>
        <DialogContent className="glass border-glass-border">
          <DialogHeader>
            <DialogTitle className="text-foreground text-sm">new folder</DialogTitle>
            <DialogDescription className="text-muted-foreground text-xs">
              in <code className="text-foreground">{currentPath}</code>
            </DialogDescription>
          </DialogHeader>
          <div className="py-3 space-y-1">
            <Label className="text-muted-foreground text-xs">name</Label>
            <Input
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              placeholder="documents"
              className="glass border-glass-border text-foreground h-8 text-xs"
              onKeyDown={(e) => { if (e.key === 'Enter') handleCreateFolder(); }}
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowNewFolderDialog(false)} className="glass border-glass-border text-foreground h-8 text-xs">
              cancel
            </Button>
            <Button onClick={handleCreateFolder} className="h-8 text-xs">create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Rename Dialog */}
      <Dialog open={showRenameDialog} onOpenChange={setShowRenameDialog}>
        <DialogContent className="glass border-glass-border">
          <DialogHeader>
            <DialogTitle className="text-foreground text-sm">rename</DialogTitle>
            <DialogDescription className="text-muted-foreground text-xs">
              rename <code className="text-foreground">{renameTarget?.name}</code>
            </DialogDescription>
          </DialogHeader>
          <div className="py-3 space-y-1">
            <Label className="text-muted-foreground text-xs">new name</Label>
            <Input
              value={renameName}
              onChange={(e) => setRenameName(e.target.value)}
              className="glass border-glass-border text-foreground h-8 text-xs"
              onKeyDown={(e) => { if (e.key === 'Enter') handleRename(); }}
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowRenameDialog(false)} className="glass border-glass-border text-foreground h-8 text-xs">
              cancel
            </Button>
            <Button onClick={handleRename} className="h-8 text-xs">rename</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent className="glass border-glass-border">
          <DialogHeader>
            <DialogTitle className="text-foreground text-sm">delete {deleteTarget?.type === 'folder' ? 'folder' : 'file'}</DialogTitle>
            <DialogDescription className="text-muted-foreground text-xs">
              permanently delete <code className="text-foreground">{deleteTarget?.name}</code>?
              {deleteTarget?.type === 'folder' && ' this will delete all contents inside.'}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteDialog(false)} className="glass border-glass-border text-foreground h-8 text-xs">
              cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} className="h-8 text-xs">delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}