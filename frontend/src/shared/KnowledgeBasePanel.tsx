import { useState, useEffect, useRef } from 'react';
import * as Dialog from '@radix-ui/react-popover'; // Using popover or dialog? Let's use Dialog for consistency
import * as RadixDialog from '@radix-ui/react-dialog';
import {
  Database,
  Upload,
  Trash2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  FileText,
  ChevronDown,
  ChevronUp,
  BookOpen,
  Sparkles,
  X
} from 'lucide-react';

interface KBDocument {
  id: string;
  filename: string;
  file_size: number;
  status: string;
  reason: string | null;
  confidence: number | null;
  chunk_count: number;
  uploaded_at: string | null;
}

interface KBStatus {
  workspace: string;
  status: string;
  document_count: number;
  chunk_count: number;
  name: string;
}

interface KnowledgeBasePanelProps {
  isOpen: boolean;
  onClose: () => void;
  apiBaseUrl: string; // e.g. "/compliance/api/knowledge-base"
  workspace: 'compliance' | 'banking';
}

export function KnowledgeBasePanel({
  isOpen,
  onClose,
  apiBaseUrl,
  workspace,
}: KnowledgeBasePanelProps) {
  const [kbStatus, setKbStatus] = useState<KBStatus | null>(null);
  const [documents, setDocuments] = useState<KBDocument[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState<string | null>(null);
  const [isClearing, setIsClearing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const accentColor = workspace === 'compliance' ? '#047857' : '#1E3A8A';
  const accentColorLight = workspace === 'compliance' ? '#F0FDF4' : '#EFF6FF';

  // Fetch KB status
  const fetchStatus = async () => {
    try {
      const res = await fetch(`${apiBaseUrl}/status`);
      if (res.ok) {
        const data = await res.json();
        setKbStatus(data);
      }
    } catch {
      // silent
    }
  };

  // Fetch documents
  const fetchDocuments = async () => {
    try {
      const res = await fetch(`${apiBaseUrl}/documents`);
      if (res.ok) {
        const data = await res.json();
        setDocuments(data.documents || []);
      }
    } catch {
      // silent
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchStatus();
      fetchDocuments();
    }
  }, [isOpen]);

  // Upload handler
  const handleUpload = async (file: File) => {
    setIsUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${apiBaseUrl}/upload`, {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();

      if (res.ok && data.success) {
        setUploadSuccess(`"${file.name}" added successfully.`);
        fetchStatus();
        fetchDocuments();
      } else {
        setUploadError(data.detail || data.error || 'Upload failed.');
      }
    } catch (err: any) {
      setUploadError(err.message || 'Failed to upload document.');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDelete = async (docId: string) => {
    setIsDeleting(docId);
    try {
      const res = await fetch(`${apiBaseUrl}/documents/${docId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        fetchStatus();
        fetchDocuments();
      }
    } catch {
      // silent
    } finally {
      setIsDeleting(null);
    }
  };

  const handleClear = async () => {
    if (!confirm('Are you sure you want to clear the entire knowledge base?')) return;
    setIsClearing(true);
    try {
      const res = await fetch(`${apiBaseUrl}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        fetchStatus();
        fetchDocuments();
        setUploadSuccess(null);
        setUploadError(null);
      }
    } catch {
      // silent
    } finally {
      setIsClearing(false);
    }
  };

  const isReady = kbStatus?.status === 'ready' && (kbStatus?.document_count ?? 0) > 0;
  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <RadixDialog.Root open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 bg-black/40 backdrop-blur-sm z-[60] animate-in fade-in duration-300" />
        <RadixDialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-2xl bg-white rounded-2xl shadow-2xl z-[70] overflow-hidden animate-in zoom-in-95 fade-in duration-300">
          
          {/* Header */}
          <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-gray-50/50">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center text-white shadow-sm" style={{ backgroundColor: accentColor }}>
                <Database className="w-5 h-5" />
              </div>
              <div>
                <RadixDialog.Title className="text-lg font-bold text-gray-900">
                  Knowledge Base Management
                </RadixDialog.Title>
                <RadixDialog.Description className="text-xs text-gray-500 font-medium">
                  {workspace === 'compliance' ? 'Regulatory standards & ground truth' : 'Banking domain context'}
                </RadixDialog.Description>
              </div>
            </div>
            <RadixDialog.Close asChild>
              <button className="p-2 hover:bg-gray-200 rounded-full transition-colors text-gray-400">
                <X className="w-5 h-5" />
              </button>
            </RadixDialog.Close>
          </div>

          <div className="max-h-[70vh] overflow-y-auto">
            {/* Status Summary */}
            <div className="p-6">
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-gray-50 p-4 rounded-xl border border-gray-100">
                  <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1">Documents</p>
                  <p className="text-2xl font-bold text-gray-900">{kbStatus?.document_count ?? 0}</p>
                </div>
                <div className="bg-gray-50 p-4 rounded-xl border border-gray-100">
                  <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1">Total Chunks</p>
                  <p className="text-2xl font-bold text-gray-900">{kbStatus?.chunk_count ?? 0}</p>
                </div>
              </div>

              {/* Upload area */}
              <div className="mt-6">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx,.doc,.txt,.md"
                  className="hidden"
                  onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])}
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading}
                  className="w-full flex flex-col items-center justify-center gap-3 p-8 rounded-2xl border-2 border-dashed transition-all hover:bg-gray-50 group"
                  style={{ borderColor: accentColor + '40', color: accentColor }}
                >
                  <div className="w-12 h-12 rounded-full flex items-center justify-center bg-gray-50 group-hover:scale-110 transition-transform">
                    {isUploading ? <Loader2 className="w-6 h-6 animate-spin" /> : <Upload className="w-6 h-6" />}
                  </div>
                  <div className="text-center">
                    <p className="font-bold">Add Reference Document</p>
                    <p className="text-xs text-gray-400 mt-1">PDF, DOCX, TXT (Max 5MB)</p>
                  </div>
                </button>

                {uploadSuccess && (
                  <div className="mt-4 p-3 bg-green-50 text-green-700 rounded-lg text-sm flex gap-2">
                    <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                    {uploadSuccess}
                  </div>
                )}
                {uploadError && (
                  <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm flex gap-2">
                    <XCircle className="w-4 h-4 flex-shrink-0" />
                    {uploadError}
                  </div>
                )}
              </div>

              {/* Document list */}
              {documents.length > 0 && (
                <div className="mt-8 space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider">Indexed Documents</h3>
                    <button onClick={handleClear} disabled={isClearing} className="text-xs text-red-500 font-bold flex items-center gap-1 hover:underline">
                      {isClearing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
                      Clear All
                    </button>
                  </div>
                  <div className="space-y-2">
                    {documents.map((doc) => (
                      <div key={doc.id} className="flex items-center justify-between p-4 rounded-xl border border-gray-100 hover:border-gray-200 transition-colors">
                        <div className="flex items-center gap-3 min-w-0">
                          <FileText className="w-5 h-5 text-gray-400" />
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-gray-900 truncate">{doc.filename}</p>
                            <p className="text-[10px] text-gray-500 uppercase font-bold tracking-tight">
                              {formatFileSize(doc.file_size)} · {doc.chunk_count} Chunks
                            </p>
                          </div>
                        </div>
                        <button onClick={() => handleDelete(doc.id)} disabled={isDeleting === doc.id} className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-500 rounded-lg transition-colors">
                          {isDeleting === doc.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Footer Footer */}
          {isReady && (
            <div className="px-6 py-4 bg-blue-50 border-t border-blue-100 flex items-center gap-3 text-blue-800 text-sm font-medium">
              <Sparkles className="w-5 h-5" />
              <span>RAG is active: This knowledge base will be used to ground evaluations.</span>
            </div>
          )}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
