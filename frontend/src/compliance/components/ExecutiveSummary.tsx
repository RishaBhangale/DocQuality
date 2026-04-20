import { useState } from 'react';
import { FileText, AlertTriangle, Lightbulb, Copy, Check } from 'lucide-react';

interface ExecutiveSummaryProps {
  executiveSummary: string;
  riskSummary: string;
  recommendations: string[];
  documentType: string;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement('textarea');
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <button
      onClick={handleCopy}
      className="flex-shrink-0 p-1.5 rounded-md text-gray-400 hover:text-[#1E3A8A] hover:bg-[#1E3A8A]/5 transition-all focus:outline-none print:hidden"
      title="Copy to clipboard"
    >
      {copied ? (
        <Check className="w-3.5 h-3.5 text-[#16A34A]" />
      ) : (
        <Copy className="w-3.5 h-3.5" />
      )}
    </button>
  );
}

export function ExecutiveSummary({
  executiveSummary,
  riskSummary,
  recommendations,
  documentType,
}: ExecutiveSummaryProps) {
  return (
    <div className="space-y-6">
      {/* Executive Summary */}
      <div className="bg-white rounded-lg p-6 sm:p-8 shadow-sm border border-gray-100">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-lg bg-[#1E3A8A]/10 flex items-center justify-center flex-shrink-0">
            <FileText className="w-5 h-5 text-[#1E3A8A]" />
          </div>
          <div className="flex-1">
            <h3 className="text-lg sm:text-xl font-semibold text-gray-900 mb-3">
              Executive Summary
            </h3>
            <p className="text-sm sm:text-base text-gray-600 leading-relaxed">
              {executiveSummary || 'No executive summary available. Configure Azure Foundry LLM for AI-assisted analysis.'}
            </p>
          </div>
        </div>
      </div>

      {/* Risk Assessment */}
      {riskSummary && (
        <div className="bg-white rounded-lg p-6 sm:p-8 shadow-sm border border-gray-100">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-lg bg-[#DC2626]/10 flex items-center justify-center flex-shrink-0">
              <AlertTriangle className="w-5 h-5 text-[#DC2626]" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg sm:text-xl font-semibold text-gray-900 mb-3">
                Risk Assessment
              </h3>
              <p className="text-sm sm:text-base text-gray-600 leading-relaxed">{riskSummary}</p>
            </div>
          </div>
        </div>
      )}

      {/* Recommendations with Copy-to-Clipboard (#3) */}
      {recommendations && recommendations.length > 0 && (
        <div className="bg-white rounded-lg p-6 sm:p-8 shadow-sm border border-gray-100">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-lg bg-[#16A34A]/10 flex items-center justify-center flex-shrink-0">
              <Lightbulb className="w-5 h-5 text-[#16A34A]" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg sm:text-xl font-semibold text-gray-900 mb-4">
                Recommendations
              </h3>
              <ul className="space-y-3">
                {recommendations.map((rec, index) => (
                  <li key={index} className="flex items-start gap-3 group">
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-[#16A34A]/10 text-[#16A34A] flex items-center justify-center text-xs font-semibold mt-0.5">
                      {index + 1}
                    </span>
                    <p className="text-sm sm:text-base text-gray-600 leading-relaxed flex-1">{rec}</p>
                    <div className="opacity-0 group-hover:opacity-100 transition-opacity mt-0.5">
                      <CopyButton text={rec} />
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
