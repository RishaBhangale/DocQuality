import { useState } from 'react';
import * as Popover from '@radix-ui/react-popover';
import { Info, X, ShieldCheck, ShieldAlert } from 'lucide-react';
import { ProgressBar } from './ProgressBar';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface BankingMetric {
  name: string;
  score: number;
  description: string;
  calculation_logic: string;
  risk_impact: string;
  reasoning?: string;
  // Enhanced fields
  metric_code?: string;
  confidence?: number;
  deterministic_score?: number;
  llm_score?: number;
  regulatory_pass_threshold?: number | null;
  regulatory_reference?: string;
  passes_regulatory_threshold?: boolean;
}

interface BankingMetricCardProps {
  metric: BankingMetric;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function getStatus(score: number): 'good' | 'warning' | 'critical' {
  if (score >= 80) return 'good';
  if (score >= 60) return 'warning';
  return 'critical';
}

const statusColors = {
  good: 'text-[#16A34A]',
  warning: 'text-[#CA8A04]',
  critical: 'text-[#DC2626]',
} as const;

const statusBgColors = {
  good: 'bg-[#16A34A]/10',
  warning: 'bg-[#EAB308]/10',
  critical: 'bg-[#DC2626]/10',
} as const;

const statusBorderColors = {
  good: 'border-[#16A34A]/30',
  warning: 'border-[#CA8A04]/30',
  critical: 'border-[#DC2626]/30',
} as const;

const statusLabels = {
  good: 'Pass',
  warning: 'Review',
  critical: 'Critical',
} as const;

// ── Component ─────────────────────────────────────────────────────────────────

export function BankingMetricCard({ metric }: BankingMetricCardProps) {
  const status = getStatus(metric.score);
  const [popoverOpen, setPopoverOpen] = useState(false);

  const passesRegThreshold = metric.passes_regulatory_threshold !== false;
  const regThreshold = metric.regulatory_pass_threshold;
  const regRef = metric.regulatory_reference;
  const confidenceRaw = metric.confidence ?? 1.0;
  const confidence = confidenceRaw > 1 ? confidenceRaw / 100 : confidenceRaw;
  const confidencePct = Math.round(confidence * 100);

  // Highlight border in red when below regulatory threshold
  const borderClass = !passesRegThreshold
    ? 'border-[#DC2626]/60 shadow-[#DC2626]/10'
    : statusBorderColors[status];

  return (
    <div
      className={`bg-white rounded-lg p-6 shadow-sm hover:shadow-lg border transition-all duration-200 ${borderClass}`}
    >
      {/* Header row */}
      <div className="flex items-start justify-between mb-3 gap-2">
        <h3 className="text-base font-semibold text-gray-900 leading-snug flex-1">
          {metric.name}
        </h3>

        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Score badge */}
          <span
            className={`px-2.5 py-1 rounded-md text-sm font-semibold ${statusBgColors[status]} ${statusColors[status]}`}
          >
            {metric.score}%
          </span>

          {/* Info popover trigger */}
          <Popover.Root open={popoverOpen} onOpenChange={setPopoverOpen}>
            <Popover.Trigger asChild>
              <button
                aria-label={`More information about ${metric.name}`}
                className="w-7 h-7 rounded-full flex items-center justify-center text-gray-400 hover:text-[#1E3A8A] hover:bg-[#1E3A8A]/10 transition-colors"
              >
                <Info className="w-4 h-4" />
              </button>
            </Popover.Trigger>

            <Popover.Portal>
              <Popover.Content
                sideOffset={8}
                align="end"
                className="z-50 w-80 rounded-lg bg-white border border-gray-200 shadow-xl p-4 text-sm"
              >
                <div className="flex items-start justify-between mb-3">
                  <span className="font-semibold text-gray-900 leading-snug pr-4">
                    {metric.name}
                  </span>
                  <Popover.Close asChild>
                    <button className="text-gray-400 hover:text-gray-600 flex-shrink-0" aria-label="Close">
                      <X className="w-4 h-4" />
                    </button>
                  </Popover.Close>
                </div>

                <div className="space-y-3">
                  <div>
                    <p className="text-xs font-semibold text-[#1E3A8A] uppercase tracking-wide mb-1">What it measures</p>
                    <p className="text-gray-700 leading-relaxed">{metric.description}</p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-[#1E3A8A] uppercase tracking-wide mb-1">How it is calculated</p>
                    <p className="text-gray-700 leading-relaxed">{metric.calculation_logic}</p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-[#DC2626] uppercase tracking-wide mb-1">Risk impact</p>
                    <p className="text-gray-700 leading-relaxed">{metric.risk_impact}</p>
                  </div>

                  {/* Score breakdown */}
                  {metric.deterministic_score !== undefined && metric.llm_score !== undefined && (
                    <div className="pt-2 border-t border-gray-100">
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Score breakdown (70/30)</p>
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div className="bg-gray-50 rounded px-2 py-1">
                          <span className="text-gray-500">Deterministic: </span>
                          <span className="font-medium">{metric.deterministic_score}</span>
                        </div>
                        <div className="bg-gray-50 rounded px-2 py-1">
                          <span className="text-gray-500">LLM: </span>
                          <span className="font-medium">{metric.llm_score}</span>
                        </div>
                      </div>

                      <div className="mt-2 bg-gray-50 rounded px-2 py-1 text-xs">
                        <span className="text-gray-500">AI confidence: </span>
                        <span className="font-medium">{confidencePct}%</span>
                        <span className="text-gray-400"> (alignment rule↔LLM)</span>
                      </div>
                    </div>
                  )}

                  {metric.reasoning && (
                    <div className="pt-2 border-t border-gray-100">
                      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Evaluation trace</p>
                      <p className="text-gray-500 text-xs leading-relaxed italic">{metric.reasoning}</p>
                    </div>
                  )}
                </div>

                <Popover.Arrow className="fill-white" />
              </Popover.Content>
            </Popover.Portal>
          </Popover.Root>
        </div>
      </div>

      {/* Regulatory Threshold Badge */}
      {regThreshold !== null && regThreshold !== undefined && (
        <div className="mb-3">
          <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
            passesRegThreshold
              ? 'bg-green-50 text-green-700 border-green-200'
              : 'bg-red-50 text-red-700 border-red-200'
          }`}>
            {passesRegThreshold
              ? <ShieldCheck className="w-3.5 h-3.5" />
              : <ShieldAlert className="w-3.5 h-3.5" />
            }
            {passesRegThreshold ? 'Reg. Pass' : 'Below Threshold'} ≥{regThreshold}
            {regRef && <span className="opacity-70 pl-1">| {regRef}</span>}
          </div>
        </div>
      )}

      {/* Progress bar */}
      <div className="mb-3">
        <ProgressBar value={metric.score} status={status} />
      </div>

      {/* Description preview */}
      <p className="text-sm text-gray-600 mb-3 line-clamp-2">{metric.description}</p>

      {/* Footer row: status + confidence */}
      <div className="flex items-center justify-between">
        <span className={`inline-flex items-center gap-1.5 text-sm font-medium ${statusColors[status]}`}>
          <span className={`w-2 h-2 rounded-full ${
            status === 'good' ? 'bg-[#16A34A]' : status === 'warning' ? 'bg-[#CA8A04]' : 'bg-[#DC2626]'
          }`} />
          {statusLabels[status]}
        </span>

        {/* AI Confidence pill */}
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
          confidencePct >= 80
            ? 'bg-blue-50 text-blue-700'
            : confidencePct >= 60
            ? 'bg-amber-50 text-amber-700'
            : 'bg-red-50 text-red-700'
        }`}>
          AI Confidence: {confidencePct}%
        </span>
      </div>
    </div>
  );
}

