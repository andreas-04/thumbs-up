import React, { useEffect, useState } from 'react';
import { api } from '../../services/api';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from './ui/dialog';
import { Button } from './ui/button';
import { Download, Loader2, FileX } from 'lucide-react';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const IMAGE_EXTS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp', 'ico'];
const PDF_EXTS = ['pdf'];
const BINARY_EXTS = [
  // Archives
  'zip', 'tar', 'gz', 'bz2', 'xz', '7z', 'rar', 'zst', 'lz4',
  // Executables / libraries
  'exe', 'dll', 'so', 'dylib', 'bin', 'app', 'msi', 'deb', 'rpm', 'apk', 'dmg', 'iso',
  // Office / documents
  'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'odt', 'ods', 'odp',
  // Media (non-image)
  'mp3', 'mp4', 'mkv', 'avi', 'mov', 'wmv', 'flv', 'webm', 'wav', 'flac', 'aac', 'ogg', 'm4a', 'm4v',
  // Fonts
  'ttf', 'otf', 'woff', 'woff2', 'eot',
  // 3D / CAD
  'stl', 'obj', 'fbx', 'blend', 'step', 'stp',
  // Database
  'db', 'sqlite', 'sqlite3',
  // Disk images / firmware
  'img', 'raw', 'vmdk', 'vdi', 'qcow2',
  // Java / .NET
  'jar', 'class', 'war', 'ear',
  // Python
  'pyc', 'pyo', 'whl', 'egg',
  // Misc binary
  'o', 'a', 'lib', 'pdb', 'dat', 'pak', 'swf',
];

function getExt(name: string): string {
  return name.split('.').pop()?.toLowerCase() ?? '';
}

export type PreviewType = 'image' | 'text' | 'pdf' | 'none';

export function getPreviewType(name: string): PreviewType {
  const ext = getExt(name);
  if (!ext) return 'none';
  if (IMAGE_EXTS.includes(ext)) return 'image';
  if (PDF_EXTS.includes(ext)) return 'pdf';
  if (BINARY_EXTS.includes(ext)) return 'none';
  return 'text';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface FilePreviewProps {
  filePath: string;
  fileName: string;
  open: boolean;
  onClose: () => void;
  onDownload: () => void;
  fetchContent?: (path: string) => Promise<Response>;
}

export default function FilePreview({ filePath, fileName, open, onClose, onDownload, fetchContent }: FilePreviewProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [textContent, setTextContent] = useState<string | null>(null);

  const previewType = getPreviewType(fileName);

  useEffect(() => {
    if (!open) return;

    // Reset
    setBlobUrl(null);
    setTextContent(null);
    setError(null);
    setLoading(true);

    let objectUrl: string | null = null;

    const load = async () => {
      try {
        const fetcher = fetchContent ?? ((p: string) => api.previewFile(p));
        const response = await fetcher(filePath.replace(/^\/+/, ''));
        if (previewType === 'text') {
          const text = await response.text();
          setTextContent(text);
        } else {
          const blob = await response.blob();
          objectUrl = URL.createObjectURL(blob);
          setBlobUrl(objectUrl);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load preview');
      } finally {
        setLoading(false);
      }
    };

    load();

    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [open, filePath]);

  // Clean up blob URL when closing
  useEffect(() => {
    if (!open && blobUrl) {
      URL.revokeObjectURL(blobUrl);
      setBlobUrl(null);
    }
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="glass border-glass-border sm:max-w-4xl max-h-[90vh] overflow-hidden flex flex-col p-0 gap-0">
        <DialogHeader className="px-4 py-3 border-b border-glass-border shrink-0">
          <div className="flex items-center gap-2 pr-8">
            <DialogTitle className="text-foreground text-sm font-mono truncate">
              {fileName}
            </DialogTitle>
            <Button
              variant="ghost"
              size="sm"
              onClick={onDownload}
              className="text-term-blue hover:text-term-cyan h-7 w-7 p-0 shrink-0"
              title="Download"
            >
              <Download className="h-3.5 w-3.5" />
            </Button>
          </div>
          <DialogDescription className="sr-only">Preview of {fileName}</DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-auto min-h-0">
          {loading && (
            <div className="flex items-center justify-center h-64">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          )}

          {error && !loading && (
            <div className="flex flex-col items-center justify-center h-64 gap-2 text-muted-foreground">
              <FileX className="h-8 w-8" />
              <span className="text-xs">{error}</span>
            </div>
          )}

          {!loading && !error && previewType === 'image' && blobUrl && (
            <div className="flex items-center justify-center p-4 bg-black/20">
              <img
                src={blobUrl}
                alt={fileName}
                className="max-w-full max-h-[70vh] object-contain rounded"
              />
            </div>
          )}

          {!loading && !error && previewType === 'text' && textContent !== null && (
            <pre className="p-4 text-xs font-mono text-foreground whitespace-pre-wrap break-words leading-relaxed">
              {textContent}
            </pre>
          )}

          {!loading && !error && previewType === 'pdf' && blobUrl && (
            <embed
              src={blobUrl}
              type="application/pdf"
              className="w-full h-[75vh]"
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
