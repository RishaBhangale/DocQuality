import { Upload, FileText, Loader2 } from 'lucide-react';
import { useRef, useState } from 'react';

interface UploadCardProps {
  onUploadComplete: (data: any) => void;
  apiEndpoint: string;
}

export function UploadCard({ onUploadComplete, apiEndpoint }: UploadCardProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();

    const files = e.dataTransfer.files;
    if (files && files[0]) {
      setSelectedFile(files[0]);
      setError(null);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files[0]) {
      setSelectedFile(files[0]);
      setError(null);
    }
  };

  const handleClick = () => {
    if (!isUploading) {
      fileInputRef.current?.click();
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const res = await fetch(apiEndpoint, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Upload failed (${res.status})`);
      }

      const data = await res.json();
      onUploadComplete(data);
    } catch (err: any) {
      setError(err.message || 'Upload failed. Please try again.');
      setIsUploading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={handleClick}
        className="w-full max-w-[600px] mx-auto border-2 border-dashed border-gray-300 rounded-xl bg-white hover:border-[#1E3A8A] hover:bg-gray-50 transition-all cursor-pointer group"
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt,.md"
          onChange={handleFileChange}
          className="hidden"
        />
        <div className="flex flex-col items-center justify-center py-12 px-6 sm:px-8">
          <div className="w-16 h-16 rounded-full bg-[#1E3A8A]/10 flex items-center justify-center mb-6 group-hover:bg-[#1E3A8A]/20 transition-colors">
            <Upload className="w-8 h-8 text-[#1E3A8A]" />
          </div>
          {selectedFile ? (
            <div className="text-center">
              <div className="flex items-center gap-2 mb-2 justify-center">
                <FileText className="w-5 h-5 text-blue-600" />
                <p className="text-base font-medium text-gray-900 break-all">
                  {selectedFile.name}
                </p>
              </div>
              <p className="text-sm text-gray-500">
                {(selectedFile.size / 1024 / 1024).toFixed(2)} MB — Click to change file
              </p>
            </div>
          ) : (
            <>
              <p className="text-base sm:text-lg font-medium text-gray-900 mb-2 text-center">
                Drag & drop your document here
              </p>
              <p className="text-sm sm:text-base text-gray-600 mb-4 text-center">
                or click to browse
              </p>
              <div className="text-center space-y-1">
                <p className="text-xs sm:text-sm text-gray-500">
                  Supported formats: PDF, DOCX, TXT, MD
                </p>
                <p className="text-xs sm:text-sm text-gray-500">
                  Max file size: 5MB
                </p>
              </div>
            </>
          )}
        </div>
      </div>

      {error && (
        <div className="max-w-[600px] mx-auto p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}

      {selectedFile && (
        <div className="max-w-[600px] mx-auto">
          <button
            onClick={handleUpload}
            disabled={isUploading}
            className="w-full py-3 rounded-xl font-bold text-white bg-[#1E3A8A] hover:bg-[#1E3A8A]/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2 shadow-sm"
          >
            {isUploading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Uploading & Analyzing...
              </>
            ) : (
              <>
                <Upload className="w-5 h-5" />
                Analyze Document
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}