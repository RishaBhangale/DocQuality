import { useState } from 'react';
import { ProgressBar } from './ProgressBar';
import * as Dialog from '@radix-ui/react-dialog';
import { X, ChevronRight, HelpCircle } from 'lucide-react';

interface MetricCardProps {
  name: string;
  score: number;
  description: string;
  statusMessage: string;
  status: 'good' | 'warning' | 'critical';
  explanation?: string;
  issueDetails?: string;
  standardsBadge?: string;
}

export function MetricCard({ name, score, description, statusMessage, status, explanation, issueDetails, standardsBadge }: MetricCardProps) {
  const [showTooltip, setShowTooltip] = useState(false);

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

  const scoreColor = {
    bg: statusBgColors[status],
    text: statusColors[status],
  };

  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <div className="bg-white rounded-lg p-6 shadow-sm hover:shadow-lg hover:-translate-y-1 border border-gray-100 transition-all duration-200 h-full flex flex-col text-left cursor-pointer group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1E3A8A] focus-visible:ring-offset-2">
          {/* Header with metric name, tooltip, score badge */}
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-1.5">
              <h3 className="text-lg font-semibold text-gray-900 group-hover:text-[#1E3A8A] transition-colors">{name}</h3>
              {/* #2 Tooltip */}
              {explanation && (
                <div className="relative">
                  <button
                    onMouseEnter={() => setShowTooltip(true)}
                    onMouseLeave={() => setShowTooltip(false)}
                    onClick={(e) => { e.stopPropagation(); setShowTooltip(!showTooltip); }}
                    className="text-gray-400 hover:text-[#1E3A8A] transition-colors focus:outline-none"
                    aria-label="More info"
                  >
                    <HelpCircle className="w-4 h-4" />
                  </button>
                  {showTooltip && (
                    <div className="absolute z-50 left-1/2 -translate-x-1/2 top-7 w-64 p-3 bg-gray-900 text-white text-xs rounded-lg shadow-xl leading-relaxed">
                      <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-gray-900 rotate-45" />
                      {explanation}
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className={`px-3 py-1 rounded-md text-sm font-semibold ${scoreColor.bg} ${scoreColor.text}`}>
                {score}%
              </span>
              <div className="text-gray-300 group-hover:text-[#1E3A8A] transition-colors">
                <ChevronRight className="w-5 h-5" />
              </div>
            </div>
          </div>

          <div className="mb-4">
            <ProgressBar value={score} status={status} />
          </div>

          {standardsBadge && (
            <div className="mb-3 flex flex-wrap gap-1.5">
              {standardsBadge.split(', ').map((badge, i) => (
                <span key={i} className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-[#1E3A8A]/5 text-[#1E3A8A] border border-[#1E3A8A]/10 uppercase tracking-wider">
                  {badge}
                </span>
              ))}
            </div>
          )}

          <p className="text-sm text-gray-600 mb-3 flex-1 line-clamp-2">
            {description}
          </p>

          <p className={`text-sm font-medium ${statusColors[status]}`}>
            {statusMessage}
          </p>
        </div>
      </Dialog.Trigger>

      {/* Full Detail Dialog (existing) */}
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
              <span className={`px-3 py-1 rounded-md text-base font-bold ${scoreColor.bg} ${scoreColor.text}`}>
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