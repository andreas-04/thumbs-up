import React, { useState } from 'react';
import { useData, FileItem } from '../contexts/DataContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
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
import { Badge } from '../components/ui/badge';
import { Alert, AlertDescription } from '../components/ui/alert';
import {
  FolderOpen,
  File,
  Home,
  ChevronRight,
  Search,
  Download,
  Upload,
  Lock,
  Info,
} from 'lucide-react';

export default function FileBrowser() {
  const { files, currentPath, refreshFiles, settings } = useData();
  const [searchQuery, setSearchQuery] = useState('');

  // Files from API are already for the current directory, no filtering needed
  // Filter by search
  const filteredFiles = files.filter((f) =>
    f.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Calculate path breadcrumbs
  const pathParts = currentPath.split('/').filter(Boolean);

  const navigateToFolder = (path: string) => {
    refreshFiles(path);
    setSearchQuery('');
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
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-white">File Browser</h1>
        <p className="text-gray-400 mt-1">
          Browse and manage shared files
        </p>
      </div>

      <Alert className="bg-blue-950 border-blue-900">
        <Info className="h-4 w-4 text-blue-400" />
        <AlertDescription className="text-blue-300">
          <strong>Access Mode: {settings.mode === 'open' ? 'Open' : 'Protected'}</strong>
          {' - '}
          {settings.mode === 'open' 
            ? 'All users can access files via HTTPS without authentication.'
            : 'Only approved users can access files. Authentication required.'}
        </AlertDescription>
      </Alert>

      <Card className="bg-gray-900 border-gray-800">
        <CardHeader>
          <CardTitle className="text-white">Shared Files</CardTitle>
          <CardDescription className="text-gray-400">
            Files available over HTTPS/TLS
          </CardDescription>
          
          {/* Breadcrumb Navigation */}
          <div className="pt-4 flex items-center gap-2 text-sm">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigateToFolder('/')}
              className="text-gray-300 hover:text-white"
            >
              <Home className="h-4 w-4" />
            </Button>
            {pathParts.map((part, index) => {
              const path = '/' + pathParts.slice(0, index + 1).join('/');
              return (
                <div key={path} className="flex items-center gap-2">
                  <ChevronRight className="h-4 w-4 text-gray-600" />
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => navigateToFolder(path)}
                    className="text-gray-300 hover:text-white"
                  >
                    {part}
                  </Button>
                </div>
              );
            })}
          </div>

          {/* Search */}
          <div className="pt-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                placeholder="Search files and folders..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {/* Action Buttons */}
          <div className="flex gap-2 mb-4">
            <Button size="sm" variant="outline" className="bg-gray-800 border-gray-700 text-white hover:bg-gray-700">
              <Upload className="h-4 w-4 mr-2" />
              Upload
            </Button>
            <Button size="sm" variant="outline" className="bg-gray-800 border-gray-700 text-white hover:bg-gray-700">
              <FolderOpen className="h-4 w-4 mr-2" />
              New Folder
            </Button>
          </div>

          <div className="border border-gray-800 rounded-lg overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="border-gray-800 hover:bg-gray-800/50">
                  <TableHead className="text-gray-300">Name</TableHead>
                  <TableHead className="text-gray-300">Type</TableHead>
                  <TableHead className="text-gray-300">Size</TableHead>
                  <TableHead className="text-gray-300">Modified</TableHead>
                  <TableHead className="text-right text-gray-300">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {/* Back button if not at root */}
                {currentPath !== '/' && (
                  <TableRow 
                    className="border-gray-800 hover:bg-gray-800/50 cursor-pointer"
                    onClick={() => {
                      const parentPath = currentPath.substring(0, currentPath.lastIndexOf('/')) || '/';
                      navigateToFolder(parentPath);
                    }}
                  >
                    <TableCell colSpan={5} className="text-gray-400">
                      <div className="flex items-center gap-2">
                        <FolderOpen className="h-4 w-4" />
                        <span>.. (Parent Directory)</span>
                      </div>
                    </TableCell>
                  </TableRow>
                )}

                {filteredFiles.length === 0 ? (
                  <TableRow className="border-gray-800">
                    <TableCell colSpan={5} className="text-center py-8 text-gray-500">
                      {searchQuery ? 'No files found matching your search' : 'This folder is empty'}
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredFiles
                    .sort((a, b) => {
                      // Folders first, then files
                      if (a.type !== b.type) {
                        return a.type === 'folder' ? -1 : 1;
                      }
                      return a.name.localeCompare(b.name);
                    })
                    .map((file) => (
                      <TableRow 
                        key={file.id} 
                        className="border-gray-800 hover:bg-gray-800/50 cursor-pointer"
                        onClick={() => handleFileClick(file)}
                      >
                        <TableCell className="font-medium text-white">
                          <div className="flex items-center gap-2">
                            {file.type === 'folder' ? (
                              <FolderOpen className="h-4 w-4 text-orange-400" />
                            ) : (
                              <File className="h-4 w-4 text-blue-400" />
                            )}
                            {file.name}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant={file.type === 'folder' ? 'default' : 'secondary'}>
                            {file.type}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-gray-400">
                          {formatFileSize(file.size)}
                        </TableCell>
                        <TableCell className="text-gray-400">
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
                              className="text-blue-400 hover:text-blue-300"
                            >
                              <Download className="h-4 w-4" />
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
          <div className="mt-4 flex items-center justify-between text-sm text-gray-400">
            <div>
              {filteredFiles.length} item{filteredFiles.length !== 1 ? 's' : ''}
              {' '}
              ({filteredFiles.filter((f) => f.type === 'folder').length} folder
              {filteredFiles.filter((f) => f.type === 'folder').length !== 1 ? 's' : ''},
              {' '}
              {filteredFiles.filter((f) => f.type === 'file').length} file
              {filteredFiles.filter((f) => f.type === 'file').length !== 1 ? 's' : ''})
            </div>
            <div className="flex items-center gap-2">
              <Lock className="h-4 w-4 text-green-400" />
              <span>TLS {settings.tlsEnabled ? 'Enabled' : 'Disabled'}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Connection Info */}
      <Card className="bg-gray-900 border-gray-800">
        <CardHeader>
          <CardTitle className="text-white">Access Information</CardTitle>
          <CardDescription className="text-gray-400">
            How users can access these files
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="p-3 bg-gray-800 rounded-lg">
            <div className="text-sm text-gray-300 mb-1">HTTPS URL:</div>
            <code className="text-sm text-blue-400">
              https://raspberrypi.local:{settings.httpsPort}/files
            </code>
          </div>
          <div className="p-3 bg-gray-800 rounded-lg">
            <div className="text-sm text-gray-300 mb-1">Access Mode:</div>
            <div className="text-sm text-white">
              {settings.mode === 'open' ? (
                <span className="text-green-400">Open Mode - No authentication required</span>
              ) : (
                <span className="text-blue-400">
                  Protected Mode - {settings.authMethod.split('+').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' + ')} required
                </span>
              )}
            </div>
          </div>
          <div className="p-3 bg-gray-800 rounded-lg">
            <div className="text-sm text-gray-300 mb-1">Security:</div>
            <div className="text-sm text-green-400">
              {settings.tlsEnabled ? '🔒 TLS/HTTPS encryption enabled' : '⚠️ TLS encryption disabled'}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}