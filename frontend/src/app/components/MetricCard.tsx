import { ProgressBar } from './ProgressBar';
import * as Dialog from '@radix-ui/react-dialog';
import { X, ChevronRight } from 'lucide-react';

interface MetricCardProps {
  name: string;
  score: number;
  description: string;
  statusMessage: string;
  status: 'good' | 'warning' | 'critical';
  explanation?: string;
  issueDetails?: string; // LLM reasoning or finding details
}

export function MetricCard({ name, score, description, statusMessage, status, explanation, issueDetails }: MetricCardProps) {
  const statusColors = {
    good: 'text-[#16A34A]',
    warning: 'text-[#CA8A04]',
    critical: 'text-[#DC2626]',
  };

  const statusBgColors = {
    good: 'bg-[#16A34A]/10',
    warning: 'bg-[#EAB308]/10',
    critical: 'bg-[#DC2626]/10',
  };

  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <div className="bg-white rounded-lg p-6 shadow-sm hover:shadow-lg hover:-translate-y-1 border border-gray-100 transition-all duration-200 h-full flex flex-col cursor-pointer group text-left">
          <div className="flex items-start justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 group-hover:text-[#1E3A8A] transition-colors">{name}</h3>
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className={`px-3 py-1 rounded-md text-sm font-semibold ${statusBgColors[status]} ${statusColors[status]}`}>
                {score}%
              </span>
              <ChevronRight className="w-5 h-5 text-gray-300 group-hover:text-[#1E3A8A] transition-colors" />
            </div>
          </div>

          <div className="mb-4">
            <ProgressBar value={score} status={status} />
          </div>

          <p className="text-sm text-gray-600 mb-3 flex-1 line-clamp-2">
            {description}
          </p>

          <p className={`text-sm font-medium ${statusColors[status]}`}>
            {statusMessage}
          </p>
        </div>
      </Dialog.Trigger>

      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 z-50" />
        <Dialog.Content className="fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-6 border bg-white p-8 shadow-2xl duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%] sm:rounded-2xl">

          <div className="flex flex-col gap-2">
            <div className="flex items-start justify-between">
              <Dialog.Title className="text-2xl font-bold text-gray-900">
                {name}
              </Dialog.Title>
              <Dialog.Close className="rounded-full p-1.5 hover:bg-gray-100 transition-colors focus:outline-none focus:ring-2 focus:ring-[#1E3A8A] ring-offset-2">
                <X className="h-5 w-5 text-gray-500" />
                <span className="sr-only">Close</span>
              </Dialog.Close>
            </div>

            <div className="flex items-center gap-3 mt-2">
              <span className={`px-3 py-1 rounded-md text-base font-bold ${statusBgColors[status]} ${statusColors[status]}`}>
                Score: {score}%
              </span>
              <span className={`text-sm font-medium ${statusColors[status]}`}>
                {statusMessage}
              </span>
            </div>
          </div>

          <div className="flex flex-col gap-6">
            {/* Description */}
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Metric Overview</h4>
              <p className="text-sm text-gray-700 leading-relaxed">
                {description}
              </p>
            </div>

            {/* AI Reasoning / Issue Details */}
            {issueDetails && (
              <div className={`p-4 rounded-xl border ${statusBgColors[status]} border-opacity-20`}>
                <h4 className={`text-xs font-semibold uppercase tracking-wider mb-2 ${statusColors[status]}`}>
                  Analysis Findings
                </h4>
                <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
                  {issueDetails}
                </p>
              </div>
            )}

            {/* How it works */}
            {explanation && (
              <div className="pt-4 border-t border-gray-100">
                <h4 className="text-xs font-semibold text-[#1E3A8A] uppercase tracking-wider mb-2">How it works</h4>
                <p className="text-sm text-gray-600 leading-relaxed">
                  {explanation}
                </p>
              </div>
            )}
          </div>

        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}