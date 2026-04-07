interface BankingMetricPoint {
  name: string;
  score: number;
  passes_regulatory_threshold?: boolean;
  regulatory_pass_threshold?: number | null;
  regulatory_reference?: string;
  metric_code?: string;
}

interface BankingRadarChartProps {
  metrics: BankingMetricPoint[];
  bankingOverallScore?: number;
  bankingDomain?: string;
}

// Extract a short code from metric name or use provided metric_code
function getCode(metric: BankingMetricPoint): string {
  if (metric.metric_code) return metric.metric_code.toUpperCase();
  const codeMap: Record<string, string> = {
    'Beneficial Ownership Tracing Index': 'BOTI',
    'Identity Establishment & Screening Score': 'IESS',
    'Customer Profile Index': 'CPI',
    'Collateral & Covenant Tracking Score': 'CCTS',
    'Historical Event Completeness': 'HEC',
    'Incident & SAR Reporting Rate': 'ISRR',
    'Recovery & Monitoring Preparedness': 'RMP',
    'Deposit Liability Index': 'DLI',
    'Quality of Earnings Score': 'QoE',
    'Financial Obligation & Solvency Index': 'FOSI',
    'Successor & Nominee Adequacy Disclosure': 'SNAD',
    'Wealth Concentration Warning': 'WCW',
    'Regulatory Mapping & Precedent': 'RMP',
    'BCBS 239 Data Lineage Score': 'DLS',
  };
  return codeMap[metric.name] ?? '';
}

export function BankingRadarChart({ metrics, bankingOverallScore, bankingDomain }: BankingRadarChartProps) {
  if (!metrics || metrics.length === 0) return null;

  // Sort: failing metrics first, then by score ascending so weakest are most visible
  const sorted = [...metrics].sort((a, b) => {
    const aFail = a.passes_regulatory_threshold === false ? 0 : 1;
    const bFail = b.passes_regulatory_threshold === false ? 0 : 1;
    if (aFail !== bFail) return aFail - bFail;
    return a.score - b.score;
  });

  const failingCount = metrics.filter((m) => m.passes_regulatory_threshold === false).length;
  const passingCount = metrics.length - failingCount;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">

      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">Domain Metrics Scorecard</h3>
          {bankingDomain && (
            <p className="text-xs font-medium text-[#1E3A8A] mt-0.5">{bankingDomain}</p>
          )}
        </div>
        {/* Overall domain score — clearly labelled */}
        {bankingOverallScore !== undefined && (
          <div className="shrink-0 rounded-xl border border-slate-200 bg-slate-50 px-4 py-2 text-center">
            <p className="text-2xl font-extrabold text-[#1E3A8A] leading-none">{Math.round(bankingOverallScore)}<span className="text-sm font-medium text-slate-400">/100</span></p>
            <p className="mt-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">Overall Domain Score</p>
          </div>
        )}
      </div>

      {/* ── Status summary strip ────────────────────────────────── */}
      <div className="mb-5 flex items-center gap-4 rounded-lg border border-slate-100 bg-slate-50 px-4 py-2.5">
        <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-700">
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
          {passingCount} Metric{passingCount !== 1 ? 's' : ''} Pass
        </span>
        {failingCount > 0 && (
          <span className="flex items-center gap-1.5 text-xs font-semibold text-red-700">
            <span className="h-2 w-2 rounded-full bg-red-500" />
            {failingCount} Below Regulatory Threshold
          </span>
        )}
        <span className="ml-auto flex items-center gap-3 text-[11px] text-slate-400">
          <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-sm bg-[#1E3A8A]/70" /> Score</span>
          <span className="flex items-center gap-1"><span className="inline-block h-px w-4 border-t-2 border-dashed border-slate-400" /> Reg. Threshold</span>
        </span>
      </div>

      {/* ── Per-metric bars ─────────────────────────────────────── */}
      <div className="space-y-4">
        {sorted.map((metric) => {
          const passes = metric.passes_regulatory_threshold !== false;
          const threshold = metric.regulatory_pass_threshold ?? 75;
          const score = metric.score;
          const code = getCode(metric);
          const barColor = passes ? '#1E3A8A' : '#DC2626';
          const badgeCls = passes
            ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
            : 'border-red-200 bg-red-50 text-red-700';

          return (
            <div key={metric.name}>
              {/* Label row */}
              <div className="flex items-center justify-between mb-1.5 gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  {code && (
                    <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold tracking-wide text-slate-500">
                      {code}
                    </span>
                  )}
                  <span className="truncate text-sm font-medium text-slate-700" title={metric.name}>
                    {metric.name}
                  </span>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <span className={`text-sm font-extrabold ${passes ? 'text-[#1E3A8A]' : 'text-red-600'}`}>
                    {score}
                  </span>
                  <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${badgeCls}`}>
                    {passes ? '✓ Pass' : '✗ Fail'}
                  </span>
                </div>
              </div>

              {/* Bar track */}
              <div className="relative h-5 w-full overflow-visible rounded-full bg-slate-100">
                {/* Score fill */}
                <div
                  className="absolute inset-y-0 left-0 rounded-full transition-all duration-700"
                  style={{ width: `${score}%`, backgroundColor: barColor, opacity: 0.85 }}
                />
                {/* Threshold marker line */}
                <div
                  className="absolute inset-y-[-3px] w-0.5 rounded-full bg-slate-500"
                  style={{ left: `${threshold}%` }}
                  title={`Regulatory threshold: ${threshold}`}
                />
                {/* Score text inside bar */}
                {score > 10 && (
                  <span className="absolute inset-y-0 left-2 flex items-center text-[11px] font-bold text-white/90">
                    {score}/100
                  </span>
                )}
              </div>

              {/* Sub-label: threshold reference */}
              <div className="mt-1 flex items-center gap-1 text-[11px] text-slate-400">
                <span
                  className="inline-block h-px w-3 border-t-2 border-dashed border-slate-400"
                />
                <span>
                  Threshold {threshold}
                  {metric.regulatory_reference ? ` · ${metric.regulatory_reference}` : ''}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
