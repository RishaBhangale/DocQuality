import { AlertTriangle, Info } from 'lucide-react';
import { ScoreCircle } from './ScoreCircle';

interface QualityDimensionsRowProps {
  integrityScore: number;
  standardsScore: number | null;
  integrityLabel?: string;
  standardsLabel?: string;
  primaryColor: string;
  issuesSummary?: {
    total: number;
    critical: number;
    warning: number;
    mostAffected?: string | null;
  };
  reviewInfo?: {
    reviewedAt?: string | null;
    filename?: string | null;
    evaluationId?: string | null;
  };
}

function bandFromScore(score: number): 'good' | 'warning' | 'critical' {
  if (score >= 80) return 'good';
  if (score >= 60) return 'warning';
  return 'critical';
}

const BAND_STYLES: Record<'good' | 'warning' | 'critical', { text: string; border: string; bg: string }> = {
  good: { text: '#16A34A', border: '#16A34A66', bg: '#16A34A12' },
  warning: { text: '#CA8A04', border: '#EAB30866', bg: '#EAB30812' },
  critical: { text: '#DC2626', border: '#DC262666', bg: '#DC262612' },
};

export function QualityDimensionsRow({
  integrityScore,
  standardsScore,
  integrityLabel = 'Document integrity score',
  standardsLabel = 'AI risk assessment quality',
  primaryColor,
  issuesSummary,
  reviewInfo,
}: QualityDimensionsRowProps) {
  const tileBase = 'bg-white rounded-xl border border-gray-100 shadow-sm p-5 h-full min-h-[156px]';
  const integrityBand = bandFromScore(integrityScore);
  const standardsBand = standardsScore != null ? bandFromScore(standardsScore) : 'warning';
  const integrityPill = BAND_STYLES[integrityBand];
  const standardsPill = BAND_STYLES[standardsBand];
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className={`${tileBase} flex flex-col sm:flex-row items-center gap-5`}>
        <ScoreCircle score={integrityScore} size="md" statusBand={bandFromScore(integrityScore)} />
        <div className="text-center sm:text-left flex-1 min-w-0">
          <p className="text-[11px] font-bold uppercase tracking-widest text-gray-400 mb-1">
            Quality dimensions
          </p>
          <h3 className="text-base font-bold text-gray-900 leading-snug">{integrityLabel}</h3>
          <p className="text-sm text-gray-500 mt-1">Based on universal quality metrics</p>
          <span
            className="inline-flex mt-2 text-xs font-semibold px-2.5 py-0.5 rounded-md border"
            style={{
              color: integrityPill.text,
              borderColor: integrityPill.border,
              backgroundColor: integrityPill.bg,
            }}
          >
            Quality status
          </span>
        </div>
      </div>

      {standardsScore != null && (
        <div className={`${tileBase} flex flex-col sm:flex-row items-center gap-5`}>
          <ScoreCircle score={standardsScore} size="md" statusBand={bandFromScore(standardsScore)} />
          <div className="text-center sm:text-left flex-1 min-w-0">
            <p className="text-[11px] font-bold uppercase tracking-widest text-gray-400 mb-1">
              Quality dimensions
            </p>
            <h3 className="text-base font-bold text-gray-900 leading-snug">{standardsLabel}</h3>
            <p className="text-sm text-gray-500 mt-1">Based on framework-specific standards</p>
            <span
              className="inline-flex mt-2 text-xs font-semibold px-2.5 py-0.5 rounded-md border"
              style={{
                color: standardsPill.text,
                borderColor: standardsPill.border,
                backgroundColor: standardsPill.bg,
              }}
            >
              Quality status
            </span>
          </div>
        </div>
      )}

      {issuesSummary && (
        <div className={`${tileBase} flex items-start gap-4`}>
          <div className="flex-1 min-w-0">
            <p className="text-[11px] font-bold uppercase tracking-widest text-gray-400 mb-1">
              Issues flagged
            </p>
            <div className="flex items-start gap-4">
              <span className="text-3xl font-bold text-gray-900 leading-none">{issuesSummary.total}</span>
              <div className="space-y-1 text-xs font-semibold">
                <div className="text-[#DC2626]">{issuesSummary.critical} Critical</div>
                <div className="text-[#CA8A04]">{issuesSummary.warning} Moderate</div>
              </div>
            </div>
            <p className="text-xs text-gray-500 mt-3">
              Most affected: {issuesSummary.mostAffected || 'N/A'}
            </p>
          </div>
          <div className="w-12 h-12 rounded-full bg-[#DC2626]/10 flex items-center justify-center flex-shrink-0">
            <AlertTriangle className="w-5 h-5 text-[#DC2626]" />
          </div>
        </div>
      )}

      {reviewInfo && (
        <div className={`${tileBase} flex items-start gap-4`}>
          <div className="w-12 h-12 rounded-full bg-[#1E3A8A]/10 flex items-center justify-center flex-shrink-0">
            <Info className="w-5 h-5 text-[#1E3A8A]" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[11px] font-bold uppercase tracking-widest text-gray-400 mb-2">
              Review information
            </p>
            <div className="grid grid-cols-[90px_1fr] gap-y-2 text-xs text-gray-600">
              <span className="text-gray-400">Review date:</span>
              <span className="font-semibold text-gray-900">{reviewInfo.reviewedAt || '—'}</span>
              <span className="text-gray-400">File:</span>
              <span className="font-semibold text-gray-900 truncate">{reviewInfo.filename || '—'}</span>
              <span className="text-gray-400">ID:</span>
              <span className="font-mono text-[11px] font-semibold text-gray-700 bg-gray-100 px-2 py-0.5 rounded w-fit">
                {reviewInfo.evaluationId || '—'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
