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
  Lock,
  Loader2,
} from 'lucide-react';
import { toast } from 'sonner';

export default function FileBrowser() {
  const { files, currentPath, refreshFiles, settings } = useData();
  const [searchQuery, setSearchQuery] = useState('');
  const [showNewFolderDialog, setShowNewFolderDialog] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files;
    if (!selectedFiles || selectedFiles.length === 0) return;

    setUploading(true);
    try {
      // API expects a relative path without leading slash; root is empty string
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
      // Reset input so re-selecting the same file triggers onChange
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
      // API expects a relative path without leading slash; root is empty string
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

  if (!settings) return null;

  // Files from API are already for the current directory, no filtering needed
  // Filter by search
  const filteredFiles = files.filter((f) =>
    f.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Calculate path breadcrumbs
  const pathParts = currentPath.split('/').filter(Boolean);

  const navigateToFolder = (path: string) => {
    // Normalize path to always have a leading slash
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
    // Create a download link using the API endpoint
    const token = localStorage.getItem('auth_token');
    const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
    const url = `${baseUrl}/api/v1/files/download?path=${encodeURIComponent(filePath)}`;
    
    // Create a temporary anchor element to trigger the download
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    
    // If we have a token, we need to fetch with auth and create a blob URL
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
      // No auth needed, direct download
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
                  <TableHead className="text-muted-foreground text-xs">name</TableHead>
                  <TableHead className="text-muted-foreground text-xs hidden sm:table-cell">size</TableHead>
                  <TableHead className="text-muted-foreground text-xs hidden sm:table-cell">modified</TableHead>
                  <TableHead className="text-right text-muted-foreground text-xs w-12"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {/* Back button if not at root */}
                {currentPath !== '/' && (
                  <TableRow 
                    className="border-glass-border hover:bg-glass-highlight cursor-pointer"
                    onClick={goBack}
                  >
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
                    <TableCell colSpan={4} className="text-center py-6 text-muted-foreground text-xs">
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
                    .map((file) => (
                      <TableRow 
                        key={file.id || file.path} 
                        className="border-glass-border hover:bg-glass-highlight cursor-pointer"
                        onClick={() => handleFileClick(file)}
                      >
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
                        </TableCell>
                      </TableRow>
                    ))
                )}
              </TableBody>
            </Table>
          </div>

          {/* File Stats */}
          <div className="mt-3 text-xs text-muted-foreground">
            {filteredFiles.length} item{filteredFiles.length !== 1 ? 's' : ''}
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
    </div>
  );
}