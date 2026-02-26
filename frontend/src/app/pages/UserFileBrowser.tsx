import { useState, useEffect } from 'react';
import {
  FolderOpen,
  File,
  Home,
  ChevronRight,
  Search,
  Download,
  Upload,
  RefreshCw,
  Loader2,
  Lock,
  HardDrive,
  LogOut,
} from 'lucide-react';
import { useNavigate } from 'react-router';
import { api } from '../../services/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
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
import { Alert, AlertDescription } from '../components/ui/alert';
import { useAuth } from '../contexts/AuthContext';

interface FileItem {
  id: string;
  name: string;
  type: 'folder' | 'file';
  path: string;
  size?: number;
  modifiedAt: string;
}

export default function UserFileBrowser() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileItems, setFileItems] = useState<FileItem[]>([]);
  const [currentPath, setCurrentPath] = useState('/');
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const loadFiles = async (path: string = '/') => {
    setLoading(true);
    setError(null);
    try {
      const apiPath = path === '/' ? '' : path.replace(/^\//, '');
      const { files } = await api.listFiles({ path: apiPath });
      setFileItems(files.map(f => ({
        id: f.id || f.path,
        name: f.name,
        type: f.type,
        path: f.path,
        size: f.size,
        modifiedAt: f.modifiedAt,
      })));
      setCurrentPath(path);
    } catch (err) {
      console.error('Failed to load files:', err);
      setError(err instanceof Error ? err.message : 'Failed to load files');
      setFileItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFiles('/');
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setUploading(true);
    try {
      const uploadPath = currentPath === '/' ? '' : currentPath.replace(/^\//, '');
      await api.uploadFile(selectedFile, uploadPath);
      setSelectedFile(null);
      await loadFiles(currentPath);
    } catch (err) {
      console.error('Upload failed:', err);
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleItemClick = (item: FileItem) => {
    if (item.type === 'folder') {
      const newPath = item.path.startsWith('/') ? item.path : '/' + item.path;
      loadFiles(newPath);
      setSearchQuery('');
    }
  };

  const handleDownload = (item: FileItem) => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
    const url = `${baseUrl}/api/v1/files/download?path=${encodeURIComponent(item.path)}`;
    const token = localStorage.getItem('auth_token');

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
          const link = document.createElement('a');
          link.href = blobUrl;
          link.download = item.name;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          URL.revokeObjectURL(blobUrl);
        })
        .catch(err => {
          console.error('Download error:', err);
          setError('Download failed');
        });
    } else {
      const link = document.createElement('a');
      link.href = url;
      link.download = item.name;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  const goBack = () => {
    if (currentPath === '/') return;
    const parentPath = currentPath.substring(0, currentPath.lastIndexOf('/')) || '/';
    loadFiles(parentPath);
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

  const pathParts = currentPath.split('/').filter(Boolean);

  const filteredFiles = fileItems
    .filter((f) => f.name.toLowerCase().includes(searchQuery.toLowerCase()))
    .sort((a, b) => {
      if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
      return a.name.localeCompare(b.name);
    });

  const folderCount = filteredFiles.filter((f) => f.type === 'folder').length;
  const fileCount = filteredFiles.filter((f) => f.type === 'file').length;

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900">
        <div className="max-w-7xl mx-auto px-6 py-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-blue-950 flex items-center justify-center">
              <HardDrive className="h-5 w-5 text-blue-400" />
            </div>
            <div>
              <h1 className="text-xl font-semibold text-white">ThumbsUp File Share</h1>
              <p className="text-xs text-gray-400">Browse &amp; download shared files</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => loadFiles(currentPath)}
              className="text-gray-400 hover:text-white"
              title="Refresh"
            >
              <RefreshCw className={`h-5 w-5 ${loading ? 'animate-spin' : ''}`} />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={async () => { await logout(); navigate('/'); }}
              className="text-gray-400 hover:text-white"
              title="Logout"
            >
              <LogOut className="h-5 w-5 mr-1" />
              Logout
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-6">
        {/* Error */}
        {error && (
          <Alert className="bg-red-950 border-red-900">
            <AlertDescription className="text-red-300 flex items-center justify-between">
              {error}
              <Button variant="ghost" size="sm" onClick={() => setError(null)} className="text-red-400 hover:text-red-300 ml-4">
                Dismiss
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {/* Upload Card */}
        <Card className="bg-gray-900 border-gray-800">
          <CardContent className="p-4">
            <div className="flex items-center gap-4 flex-wrap">
              <div className="flex items-center gap-2 text-gray-300">
                <Upload className="h-4 w-4 text-blue-400" />
                <span className="font-medium text-sm">Upload File</span>
              </div>
              <label>
                <Button variant="outline" size="sm" className="bg-gray-800 border-gray-700 text-white hover:bg-gray-700 cursor-pointer" asChild>
                  <span>Browse…</span>
                </Button>
                <input type="file" className="hidden" onChange={handleFileSelect} />
              </label>
              <span className="text-sm text-gray-400 truncate max-w-[200px]">
                {selectedFile ? selectedFile.name : 'No file selected'}
              </span>
              <Button
                size="sm"
                onClick={handleUpload}
                disabled={!selectedFile || uploading}
              >
                {uploading && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
                Upload
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* File Browser Card */}
        <Card className="bg-gray-900 border-gray-800">
          <CardHeader>
            <CardTitle className="text-white">Files</CardTitle>
            <CardDescription className="text-gray-400">
              Browse shared files and folders
            </CardDescription>

            {/* Breadcrumb */}
            <div className="pt-4 flex items-center gap-1 text-sm flex-wrap">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => { loadFiles('/'); setSearchQuery(''); }}
                className="text-gray-300 hover:text-white"
              >
                <Home className="h-4 w-4" />
              </Button>
              {pathParts.map((part, index) => {
                const path = '/' + pathParts.slice(0, index + 1).join('/');
                return (
                  <div key={path} className="flex items-center gap-1">
                    <ChevronRight className="h-4 w-4 text-gray-600" />
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => { loadFiles(path); setSearchQuery(''); }}
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
                  placeholder="Search files and folders…"
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
                    <TableHead className="text-gray-300">Name</TableHead>
                    <TableHead className="text-gray-300">Type</TableHead>
                    <TableHead className="text-gray-300">Size</TableHead>
                    <TableHead className="text-gray-300">Modified</TableHead>
                    <TableHead className="text-right text-gray-300">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {/* Parent directory row */}
                  {currentPath !== '/' && (
                    <TableRow
                      className="border-gray-800 hover:bg-gray-800/50 cursor-pointer"
                      onClick={goBack}
                    >
                      <TableCell colSpan={5} className="text-gray-400">
                        <div className="flex items-center gap-2">
                          <FolderOpen className="h-4 w-4" />
                          <span>.. (Parent Directory)</span>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}

                  {loading ? (
                    <TableRow className="border-gray-800">
                      <TableCell colSpan={5} className="text-center py-12">
                        <Loader2 className="h-6 w-6 text-gray-400 animate-spin mx-auto" />
                      </TableCell>
                    </TableRow>
                  ) : filteredFiles.length === 0 ? (
                    <TableRow className="border-gray-800">
                      <TableCell colSpan={5} className="text-center py-8 text-gray-500">
                        {searchQuery ? 'No files found matching your search' : 'This folder is empty'}
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredFiles.map((item) => (
                      <TableRow
                        key={item.id}
                        className="border-gray-800 hover:bg-gray-800/50 cursor-pointer"
                        onClick={() => handleItemClick(item)}
                      >
                        <TableCell className="font-medium text-white">
                          <div className="flex items-center gap-2">
                            {item.type === 'folder' ? (
                              <FolderOpen className="h-4 w-4 text-orange-400" />
                            ) : (
                              <File className="h-4 w-4 text-blue-400" />
                            )}
                            {item.name}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant={item.type === 'folder' ? 'default' : 'secondary'}>
                            {item.type}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-gray-400">
                          {formatFileSize(item.size)}
                        </TableCell>
                        <TableCell className="text-gray-400">
                          {new Date(item.modifiedAt).toLocaleDateString()}
                        </TableCell>
                        <TableCell className="text-right">
                          {item.type === 'file' && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDownload(item);
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

            {/* Footer stats */}
            <div className="mt-4 flex items-center justify-between text-sm text-gray-400">
              <div>
                {filteredFiles.length} item{filteredFiles.length !== 1 ? 's' : ''}
                {' '}({folderCount} folder{folderCount !== 1 ? 's' : ''}, {fileCount} file{fileCount !== 1 ? 's' : ''})
              </div>
              <div className="flex items-center gap-2">
                <Lock className="h-4 w-4 text-green-400" />
                <span>Secure Connection</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
