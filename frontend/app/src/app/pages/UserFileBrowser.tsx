import { useState, useEffect } from 'react';
import { Folder, FileText, Upload, Settings, Download, User, ChevronLeft, RefreshCw, Loader2 } from 'lucide-react';
import { api, FileItem as ApiFileItem } from '../../services/api';

interface FileItem {
  id: string;
  name: string;
  type: 'folder' | 'file';
  path: string;
  size?: number;
  modifiedAt: string;
}

export default function UserFileBrowser() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileItems, setFileItems] = useState<FileItem[]>([]);
  const [currentPath, setCurrentPath] = useState('/');
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      // No auth needed, direct download
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

  const formatDate = (dateString: string): string => {
    try {
      const date = new Date(dateString);
      return date.toLocaleString();
    } catch {
      return dateString;
    }
  };

  return (
    <div className="h-screen flex flex-col dark bg-gray-900">
      {/* Header */}
      <header className="bg-gray-800 border-gray-700 border-b px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Folder className="w-8 h-8 text-gray-400" />
          <h1 className="text-2xl font-semibold text-white">ThumbsUp File Share</h1>
        </div>
        <div className="flex items-center gap-4">
          <button 
            onClick={() => loadFiles(currentPath)}
            className="p-2 hover:bg-gray-700 rounded-lg transition-all hover:scale-110"
            title="Refresh"
          >
            <RefreshCw className={`w-5 h-5 text-gray-400 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button className="p-2 hover:bg-gray-700 rounded-lg transition-all hover:scale-110">
            <Settings className="w-6 h-6 text-gray-400" />
          </button>
        </div>
      </header>

      {/* Breadcrumb / Current Path */}
      <div className="bg-gray-800 border-gray-700 border-b px-6 py-2 flex items-center gap-2">
        <button
          onClick={goBack}
          disabled={currentPath === '/'}
          className="p-1 hover:bg-gray-700 rounded disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        >
          <ChevronLeft className="w-5 h-5 text-gray-400" />
        </button>
        <span className="text-gray-300 font-mono text-sm">{currentPath}</span>
      </div>

      {/* Upload Area */}
      <div className="bg-gray-800 border-gray-700 border-b px-6 py-4">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-gray-300">
            <Upload className="w-5 h-5 text-blue-400" />
            <span className="font-medium">Upload File</span>
          </div>
          <label className="px-4 py-2 bg-gray-700 border-gray-600 hover:bg-gray-600 border rounded cursor-pointer transition-all hover:scale-105">
            <span className="text-gray-200">Browse...</span>
            <input
              type="file"
              className="hidden"
              onChange={handleFileSelect}
            />
          </label>
          <span className="text-gray-400 text-sm">
            {selectedFile ? selectedFile.name : 'No file selected.'}
          </span>
          <button
            onClick={handleUpload}
            disabled={!selectedFile || uploading}
            className="px-6 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded disabled:bg-gray-600 disabled:cursor-not-allowed transition-all hover:scale-105 disabled:hover:scale-100 flex items-center gap-2"
          >
            {uploading && <Loader2 className="w-4 h-4 animate-spin" />}
            Upload
          </button>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-red-900 border-red-700 border-b px-6 py-3 text-red-200">
          {error}
          <button onClick={() => setError(null)} className="ml-4 text-red-400 hover:text-red-300">×</button>
        </div>
      )}

      {/* File List */}
      <div className="flex-1 overflow-auto px-6 py-4 scrollbar-thin scrollbar-thumb-gray-400 scrollbar-track-gray-200">
        <div className="bg-gray-800 border-gray-700 rounded-lg border">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-gray-400 animate-spin" />
            </div>
          ) : fileItems.length === 0 ? (
            <div className="flex items-center justify-center py-12 text-gray-400">
              This folder is empty
            </div>
          ) : (
            fileItems.map((item) => (
              <div
                key={item.id}
                className="flex items-center gap-4 px-6 py-4 border-gray-700 hover:bg-gray-700 border-b last:border-b-0 transition-all hover:scale-[1.02] cursor-pointer"
                onClick={() => handleItemClick(item)}
              >
                {/* Icon and Name */}
                <div className="flex items-center gap-3 min-w-[300px]">
                  {item.type === 'folder' ? (
                    <Folder className="w-6 h-6 text-gray-400 flex-shrink-0" />
                  ) : (
                    <FileText className="w-6 h-6 text-gray-400 flex-shrink-0" />
                  )}
                  <span className="font-medium text-white">{item.name}</span>
                </div>

                {/* Modified Date and Size */}
                <div className="flex flex-col min-w-[200px]">
                  <span className="text-sm text-gray-400">Modified: {formatDate(item.modifiedAt)}</span>
                  {item.type === 'file' && (
                    <span className="text-sm text-gray-400">{formatFileSize(item.size)}</span>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-3 ml-auto">
                  {item.type === 'file' && (
                    <button 
                      className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded transition-all hover:scale-110"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDownload(item);
                      }}
                    >
                      <Download className="w-4 h-4 inline mr-1" />
                      Download
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
