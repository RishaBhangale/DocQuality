import { Upload } from 'lucide-react';
import { useRef } from 'react';

interface UploadCardProps {
  onFileSelect: (file: File) => void;
  selectedFile: File | null;
}

export function UploadCard({ onFileSelect, selectedFile }: UploadCardProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();

    const files = e.dataTransfer.files;
    if (files && files[0]) {
      onFileSelect(files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files[0]) {
      onFileSelect(files[0]);
    }
  };

  const handleClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      onClick={handleClick}
      className="w-full max-w-[600px] h-[260px] border-2 border-dashed border-gray-300 rounded-xl bg-white hover:border-[#1E3A8A] hover:bg-gray-50 transition-all cursor-pointer group mx-4 sm:mx-0"
    >
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.json,.txt,.csv,.xml,.html,.htm,.eml"
        onChange={handleFileChange}
        className="hidden"
      />
      <div className="flex flex-col items-center justify-center h-full px-6 sm:px-8">
        <div className="w-16 h-16 rounded-full bg-[#1E3A8A]/10 flex items-center justify-center mb-6 group-hover:bg-[#1E3A8A]/20 transition-colors">
          <Upload className="w-8 h-8 text-[#1E3A8A]" />
        </div>
        {selectedFile ? (
          <div className="text-center">
            <p className="text-base font-medium text-gray-900 mb-2 break-all px-4">
              {selectedFile.name}
            </p>
            <p className="text-sm text-gray-500">
              {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
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
                Supported: PDF, DOCX, JSON, TXT, CSV, XML, HTML, EML
              </p>
              <p className="text-xs sm:text-sm text-gray-500">
                Max file size: 5MB
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}