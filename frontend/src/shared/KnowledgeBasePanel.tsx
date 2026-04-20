import { useState, useEffect, useRef } from 'react';
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
  workspace: 'compliance' | 'banking';
  apiPrefix: string; // e.g. "/compliance/api" or "/banking/api"
  accentColor: string; // e.g. "#1E3A8A" for compliance, "#0D9488" for banking
  accentColorLight: string; // e.g. "#EFF6FF" for compliance, "#F0FDFA" for banking
}

export function KnowledgeBasePanel({
  workspace,
  apiPrefix,
  accentColor,
  accentColorLight,
}: KnowledgeBasePanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [kbStatus, setKbStatus] = useState<KBStatus | null>(null);
  const [documents, setDocuments] = useState<KBDocument[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState<string | null>(null);
  const [isClearing, setIsClearing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch KB status
  const fetchStatus = async () => {
    try {
      const res = await fetch(`${apiPrefix}/knowledge-base/status`);
      if (res.ok) {
        const data = await res.json();
        setKbStatus(data);
      }
    } catch {
      // Silently fail — KB might not be initialized yet
    }
  };

  // Fetch documents
  const fetchDocuments = async () => {
    try {
      const res = await fetch(`${apiPrefix}/knowledge-base/documents`);
      if (res.ok) {
        const data = await res.json();
        setDocuments(data.documents || []);
      }
    } catch {
      // silent
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchDocuments();
  }, []);

  // Upload handler
  const handleUpload = async (file: File) => {
    setIsUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${apiPrefix}/knowledge-base/upload`, {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();

      if (res.ok && data.success) {
        setUploadSuccess(`"${file.name}" added successfully (${data.document?.chunk_count || 0} chunks indexed).`);
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

  // Delete handler
  const handleDelete = async (docId: string) => {
    setIsDeleting(docId);
    try {
      const res = await fetch(`${apiPrefix}/knowledge-base/documents/${docId}`, {
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

  // Clear handler
  const handleClear = async () => {
    if (!confirm('Are you sure you want to clear the entire knowledge base? This cannot be undone.')) return;
    setIsClearing(true);
    try {
      const res = await fetch(`${apiPrefix}/knowledge-base`, {
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
  const validDocs = documents.filter(d => d.status === 'valid');
  const rejectedDocs = documents.filter(d => d.status === 'rejected');

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="w-full max-w-[600px] mb-6">
      {/* Collapsed summary bar */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-5 py-3 rounded-xl border transition-all duration-200 hover:shadow-md"
        style={{
          backgroundColor: isReady ? accentColorLight : '#FFFFFF',
          borderColor: isReady ? accentColor : '#E5E7EB',
        }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: isReady ? accentColor : '#9CA3AF' }}
          >
            <Database className="w-4 h-4 text-white" />
          </div>
          <div className="text-left">
            <span className="text-sm font-medium text-gray-900">
              Knowledge Base
            </span>
            {isReady ? (
              <span className="ml-2 text-xs font-medium" style={{ color: accentColor }}>
                ✓ {kbStatus!.document_count} doc{kbStatus!.document_count !== 1 ? 's' : ''} · {kbStatus!.chunk_count} chunks
              </span>
            ) : (
              <span className="ml-2 text-xs text-gray-400">
                No reference documents
              </span>
            )}
          </div>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 text-gray-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-gray-400" />
        )}
      </button>

      {/* Expanded panel */}
      {isExpanded && (
        <div className="mt-2 rounded-xl border border-gray-200 bg-white shadow-lg overflow-hidden animate-[fadeIn_0.2s_ease-out]">
          {/* Description */}
          <div className="px-5 pt-5 pb-3">
            <div className="flex items-start gap-2 text-xs text-gray-500 bg-gray-50 rounded-lg p-3">
              <BookOpen className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>
                Upload reference documents as <strong>ground truth</strong> for{' '}
                {workspace === 'compliance' ? 'AI compliance' : 'banking'} evaluations.
                Documents are domain-validated and used to enrich evaluation quality via RAG.
              </span>
            </div>
          </div>

          {/* Upload section */}
          <div className="px-5 pb-4">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.doc,.txt,.md"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleUpload(file);
              }}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg border-2 border-dashed transition-all text-sm font-medium"
              style={{
                borderColor: isUploading ? '#D1D5DB' : accentColor,
                color: isUploading ? '#9CA3AF' : accentColor,
                backgroundColor: isUploading ? '#F9FAFB' : 'transparent',
              }}
            >
              {isUploading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Validating & indexing…
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4" />
                  Add Reference Document
                </>
              )}
            </button>

            {/* Success message */}
            {uploadSuccess && (
              <div className="mt-3 flex items-start gap-2 text-xs text-green-700 bg-green-50 rounded-lg p-3">
                <CheckCircle2 className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <span>{uploadSuccess}</span>
              </div>
            )}

            {/* Error message */}
            {uploadError && (
              <div className="mt-3 flex items-start gap-2 text-xs text-red-700 bg-red-50 rounded-lg p-3">
                <XCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <span>{uploadError}</span>
              </div>
            )}
          </div>

          {/* Document list */}
          {documents.length > 0 && (
            <div className="border-t border-gray-100">
              <div className="px-5 py-3 flex items-center justify-between">
                <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Indexed Documents ({validDocs.length})
                </span>
                {validDocs.length > 0 && (
                  <button
                    onClick={handleClear}
                    disabled={isClearing}
                    className="text-xs text-red-500 hover:text-red-700 font-medium transition-colors flex items-center gap-1"
                  >
                    {isClearing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
                    Clear All
                  </button>
                )}
              </div>

              <div className="px-5 pb-4 space-y-2 max-h-[240px] overflow-y-auto">
                {documents.map((doc) => (
                  <div
                    key={doc.id}
                    className={`flex items-center justify-between p-3 rounded-lg text-sm transition-colors ${
                      doc.status === 'valid'
                        ? 'bg-gray-50 hover:bg-gray-100'
                        : 'bg-red-50/50'
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      {doc.status === 'valid' ? (
                        <CheckCircle2 className="w-4 h-4 flex-shrink-0" style={{ color: accentColor }} />
                      ) : (
                        <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                      )}
                      <div className="min-w-0">
                        <p className="text-gray-900 font-medium truncate max-w-[280px]">
                          {doc.filename}
                        </p>
                        <p className="text-gray-400 text-xs">
                          {doc.file_size ? formatFileSize(doc.file_size) : ''}
                          {doc.status === 'valid' && doc.chunk_count > 0 && ` · ${doc.chunk_count} chunks`}
                          {doc.status === 'rejected' && doc.reason && (
                            <span className="text-red-400"> · {doc.reason}</span>
                          )}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => handleDelete(doc.id)}
                      disabled={isDeleting === doc.id}
                      className="p-1 rounded hover:bg-gray-200 transition-colors flex-shrink-0"
                      title="Remove document"
                    >
                      {isDeleting === doc.id ? (
                        <Loader2 className="w-4 h-4 text-gray-400 animate-spin" />
                      ) : (
                        <Trash2 className="w-4 h-4 text-gray-400 hover:text-red-500" />
                      )}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Ready badge */}
          {isReady && (
            <div
              className="px-5 py-3 border-t flex items-center gap-2 text-xs font-medium"
              style={{ backgroundColor: accentColorLight, borderColor: '#E5E7EB', color: accentColor }}
            >
              <Sparkles className="w-4 h-4" />
              Evaluations will be enhanced with knowledge base context
            </div>
          )}
        </div>
      )}
    </div>
  );
}
