import { FileText, AlertTriangle, Lightbulb } from 'lucide-react';

interface ExecutiveSummaryProps {
  executiveSummary: string;
  riskSummary: string;
  recommendations: string[];
  documentType: string;
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

      {/* Recommendations */}
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
                  <li key={index} className="flex items-start gap-3">
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-[#16A34A]/10 text-[#16A34A] flex items-center justify-center text-xs font-semibold mt-0.5">
                      {index + 1}
                    </span>
                    <p className="text-sm sm:text-base text-gray-600 leading-relaxed">{rec}</p>
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
