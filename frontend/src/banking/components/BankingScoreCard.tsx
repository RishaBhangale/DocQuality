import { Building2, AlertTriangle, TrendingUp } from 'lucide-react';
import { getDomainQualityLabel } from '../utils/domainLabels';

interface BankingScoreCardProps {
  bankingDomain: string;
  bankingOverallScore: number;
  legalHold?: boolean;
  legalHoldReason?: string;
}

function getScoreColor(score: number) {
  if (score >= 80) return { text: 'text-green-700', bg: 'bg-green-50', ring: 'ring-green-200' };
  if (score >= 60) return { text: 'text-yellow-700', bg: 'bg-yellow-50', ring: 'ring-yellow-200' };
  return { text: 'text-red-700', bg: 'bg-red-50', ring: 'ring-red-200' };
}

function getScoreLabel(score: number) {
  if (score >= 80) return 'Compliant';
  if (score >= 60) return 'Needs Review';
  return 'Non-Compliant';
}

export function BankingScoreCard({
  bankingDomain,
  bankingOverallScore,
  legalHold = false,
  legalHoldReason = '',
}: BankingScoreCardProps) {
  const score = Math.round(bankingOverallScore);
  const colors = getScoreColor(score);

  return (
    <div className="w-full rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      {legalHold && (
        <div className="mb-4 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2.5 text-red-700">
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em]">Legal Hold Active</p>
            {legalHoldReason && <p className="mt-1 text-xs text-red-600">{legalHoldReason}</p>}
          </div>
        </div>
      )}

      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#1E3A8A]">
            <Building2 className="h-5 w-5 text-white" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Banking Score</p>
            <p className="mt-1 line-clamp-2 text-sm font-medium leading-5 text-slate-700">{bankingDomain}</p>
          </div>
        </div>
        <div className={`shrink-0 inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold ${colors.bg} ${colors.text}`}>
          <TrendingUp className="h-3.5 w-3.5" />
          {getScoreLabel(score)}
        </div>
      </div>

      <div className="mt-5 flex items-end justify-between gap-4">
        <div className="flex items-end gap-2">
          <span className={`text-5xl font-semibold leading-none ${colors.text}`}>{score}</span>
          <span className="pb-1 text-lg font-medium text-slate-400">/100</span>
        </div>
        <p className="max-w-[10rem] text-right text-xs leading-relaxed text-slate-500">
          {getDomainQualityLabel(bankingDomain).subtitle}
        </p>
      </div>

      <div className="mt-4 h-2.5 rounded-full bg-slate-100">
        <div
          className={`h-2.5 rounded-full transition-all duration-700 ${
            score >= 80 ? 'bg-green-500' : score >= 60 ? 'bg-yellow-500' : 'bg-red-500'
          }`}
          style={{ width: `${score}%` }}
        />
      </div>
    </div>
  );
}
