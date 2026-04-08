import { useState, useEffect } from 'react';
import {
  FolderOpen,
  File,
  Home,
  ChevronRight,
  Search,
  Download,
  RefreshCw,
  Loader2,
  Terminal,
  LogIn,
} from 'lucide-react';
import { useNavigate } from 'react-router';
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
import { Alert, AlertDescription } from '../components/ui/alert';

interface FileItem {
  id: string;
  name: string;
  type: 'folder' | 'file';
  path: string;
  size?: number;
  modifiedAt: string;
}

export default function GuestFileBrowser() {
  const navigate = useNavigate();
  const [fileItems, setFileItems] = useState<FileItem[]>([]);
  const [currentPath, setCurrentPath] = useState('/');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const loadFiles = async (path: string = '/') => {
    setLoading(true);
    setError(null);
    try {
      const apiPath = path === '/' ? '' : path.replace(/^\//, '');
      const { files } = await api.listGuestFiles({ path: apiPath });
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

  const handleItemClick = (item: FileItem) => {
    if (item.type === 'folder') {
      const newPath = item.path.startsWith('/') ? item.path : '/' + item.path;
      loadFiles(newPath);
      setSearchQuery('');
    }
  };

  const handleDownload = (item: FileItem) => {
    const url = api.getGuestDownloadUrl(item.path);

    const link = document.createElement('a');
    link.href = url;
    link.download = item.name;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const goBack = () => {
    if (currentPath === '/') return;
    const parts = currentPath.split('/').filter(Boolean);
    parts.pop();
    const parentPath = parts.length === 0 ? '/' : '/' + parts.join('/');
    loadFiles(parentPath);
    setSearchQuery('');
  };

  const handleSignIn = () => {
    navigate('/login');
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
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-glass-border glass">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Terminal className="h-4 w-4 text-term-green" />
            <span className="text-sm text-foreground">TerraCrate</span>
            <span className="text-xs text-muted-foreground">/ guest</span>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => loadFiles(currentPath)}
              className="text-muted-foreground hover:text-foreground h-7 w-7"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleSignIn}
              className="text-muted-foreground hover:text-foreground h-7 text-xs"
            >
              <LogIn className="h-3.5 w-3.5 mr-1" />
              sign in
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6 space-y-4">
        {/* Error */}
        {error && (
          <Alert className="glass border-glass-border">
            <AlertDescription className="text-term-red text-xs flex items-center justify-between">
              {error}
              <Button variant="ghost" size="sm" onClick={() => setError(null)} className="text-term-red hover:text-foreground h-6 text-xs ml-4">
                dismiss
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {/* File Browser */}
        <Card className="glass">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm text-foreground">files</CardTitle>

            {/* Breadcrumb */}
            <div className="pt-2 flex items-center gap-1 text-xs flex-wrap">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => { loadFiles('/'); setSearchQuery(''); }}
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
                      onClick={() => { loadFiles(path); setSearchQuery(''); }}
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

                  {loading ? (
                    <TableRow className="border-glass-border">
                      <TableCell colSpan={4} className="text-center py-8">
                        <Loader2 className="h-4 w-4 text-muted-foreground animate-spin mx-auto" />
                      </TableCell>
                    </TableRow>
                  ) : filteredFiles.length === 0 ? (
                    <TableRow className="border-glass-border">
                      <TableCell colSpan={4} className="text-center py-6 text-muted-foreground text-xs">
                        {searchQuery ? 'no matches' : 'empty'}
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredFiles.map((item) => (
                      <TableRow
                        key={item.id}
                        className="border-glass-border hover:bg-glass-highlight cursor-pointer"
                        onClick={() => handleItemClick(item)}
                      >
                        <TableCell className="text-foreground text-xs">
                          <div className="flex items-center gap-1.5">
                            {item.type === 'folder' ? (
                              <FolderOpen className="h-3.5 w-3.5 text-term-yellow" />
                            ) : (
                              <File className="h-3.5 w-3.5 text-term-blue" />
                            )}
                            {item.name}
                          </div>
                        </TableCell>
                        <TableCell className="text-muted-foreground text-xs hidden sm:table-cell">
                          {formatFileSize(item.size)}
                        </TableCell>
                        <TableCell className="text-muted-foreground text-xs hidden sm:table-cell">
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

            <div className="mt-3 text-xs text-muted-foreground">
              {filteredFiles.length} item{filteredFiles.length !== 1 ? 's' : ''}
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
