import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
} from 'recharts'
import { ShieldCheck, ShieldAlert, Scale, AlertOctagon } from 'lucide-react'
import { useMonitorAPI } from '../../hooks/useMonitorAPI'
import { ChartCard } from '../shared/ChartCard'
import { CustomTooltip, RechartsTooltip } from '../shared/CustomTooltip'
import { LoadingState, ErrorState, EmptyState } from '../shared/StateDisplays'
import type {
  ComplianceRate,
  ThresholdFailure,
  LegalHold,
  IssueSummary,
  TimeRange,
  Workspace,
} from '../../types'
import { SEVERITY_COLORS } from '../../types'

interface RegulatoryTabProps {
  timeRange: TimeRange
  workspace: Workspace
  params: Record<string, string>
}

export function RegulatoryTab({ params }: RegulatoryTabProps) {
  const compliance = useMonitorAPI<ComplianceRate>('/api/regulatory/compliance-rate', params)
  const failures = useMonitorAPI<ThresholdFailure[]>('/api/regulatory/threshold-failures', params)
  const holds = useMonitorAPI<LegalHold[]>('/api/regulatory/legal-holds', params)
  const issues = useMonitorAPI<IssueSummary[]>('/api/issues/summary', params)

  const c = compliance.data

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Top row: Compliance gauge + Issue summary */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Compliance Rate Gauge */}
        <ChartCard title="Compliance Rate" subtitle="Documents passing all thresholds">
          {compliance.loading && !c ? (
            <LoadingState />
          ) : compliance.error ? (
            <ErrorState message={compliance.error} onRetry={compliance.refetch} />
          ) : c ? (
            <div className="flex flex-col items-center justify-center h-56 gap-4">
              {/* Circular gauge */}
              <div className="relative w-36 h-36">
                <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
                  {/* Background ring */}
                  <circle
                    cx="60"
                    cy="60"
                    r="48"
                    fill="none"
                    stroke="#E8EDF6"
                    strokeWidth="10"
                  />
                  {/* Progress ring */}
                  <circle
                    cx="60"
                    cy="60"
                    r="48"
                    fill="none"
                    stroke={(c.overall_rate || 0) >= 80 ? '#22C55E' : (c.overall_rate || 0) >= 50 ? '#F59E0B' : '#EF4444'}
                    strokeWidth="10"
                    strokeLinecap="round"
                    strokeDasharray={`${((c.overall_rate || 0) / 100) * 301.6} 301.6`}
                    className="transition-all duration-1000"
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-3xl font-bold text-text-primary">
                    {c.overall_rate?.toFixed(1) ?? '—'}%
                  </span>
                  <span className="text-[10px] text-text-muted">compliant</span>
                </div>
              </div>
              <div className="flex items-center gap-6 text-xs">
                <div className="flex items-center gap-1.5">
                  <ShieldCheck size={14} className="text-accent-green" />
                  <span className="text-text-secondary">
                    {c.total_passing} pass
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <ShieldAlert size={14} className="text-accent-red" />
                  <span className="text-text-secondary">
                    {c.total_failing} fail
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <EmptyState />
          )}
        </ChartCard>

        {/* Issue Severity Summary */}
        <ChartCard title="Issue Severity" subtitle="Quality issues by severity level">
          {issues.loading && !issues.data ? (
            <LoadingState />
          ) : issues.error ? (
            <ErrorState message={issues.error} onRetry={issues.refetch} />
          ) : issues.data?.length ? (
            <div className="flex flex-col justify-center h-56 gap-3 px-2">
              {issues.data.map((issue) => {
                const color = SEVERITY_COLORS[issue.severity] ?? '#94A3B8'
                const maxCount = Math.max(...issues.data!.map((s) => s.count), 1)
                return (
                  <div key={issue.severity}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <AlertOctagon size={12} style={{ color }} />
                        <span className="text-text-primary text-xs font-medium capitalize">
                          {issue.severity}
                        </span>
                      </div>
                      <span className="text-text-secondary text-xs font-semibold">
                        {issue.count}
                      </span>
                    </div>
                    <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-700"
                        style={{
                          width: `${(issue.count / maxCount) * 100}%`,
                          backgroundColor: color,
                        }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <EmptyState />
          )}
        </ChartCard>

        {/* Threshold Failures */}
        <ChartCard title="Threshold Failures" subtitle="Metrics failing compliance thresholds">
          {failures.loading && !failures.data ? (
            <LoadingState />
          ) : failures.error ? (
            <ErrorState message={failures.error} onRetry={failures.refetch} />
          ) : failures.data?.length ? (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={failures.data} layout="vertical" barCategoryGap="20%">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" tick={{ fontSize: 11 }} />
                  <YAxis
                    type="category"
                    dataKey="metric"
                    width={90}
                    tick={{ fontSize: 10 }}
                  />
                  <RechartsTooltip content={<CustomTooltip />} />
                  <Bar
                    dataKey="failure_count"
                    name="Failures"
                    radius={[0, 6, 6, 0]}
                    fill="#EF4444"
                    fillOpacity={0.8}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState message="No threshold failures" />
          )}
        </ChartCard>
      </div>

      {/* Legal Holds Table */}
      <ChartCard title="Legal Holds" subtitle="Documents under regulatory hold">
        {holds.loading && !holds.data ? (
          <LoadingState />
        ) : holds.error ? (
          <ErrorState message={holds.error} onRetry={holds.refetch} />
        ) : holds.data?.length ? (
          <div className="max-h-72 overflow-y-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-text-muted border-b border-border-subtle">
                  <th className="text-left py-2.5 px-3 font-medium">Document</th>
                  <th className="text-left py-2.5 px-3 font-medium">Reason</th>
                  <th className="text-left py-2.5 px-3 font-medium">Created</th>
                  <th className="text-left py-2.5 px-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {holds.data.map((hold) => (
                  <tr
                    key={hold.id}
                    className="border-b border-border-subtle/50 hover:bg-slate-50 transition-colors"
                  >
                    <td className="py-2.5 px-3 text-text-primary flex items-center gap-2">
                      <Scale size={12} className="text-accent-amber shrink-0" />
                      <span className="truncate max-w-[160px]" title={hold.filename}>
                        {hold.filename}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-text-secondary truncate max-w-[200px]" title={hold.reason}>
                      {hold.reason}
                    </td>
                    <td className="py-2.5 px-3 text-text-muted whitespace-nowrap">
                      {new Date(hold.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-2 py-0.5 rounded-md text-[10px] font-medium ${
                          hold.status === 'active'
                            ? 'bg-accent-red/10 text-accent-red'
                            : 'bg-accent-green/10 text-accent-green'
                        }`}
                      >
                        {hold.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState message="No active legal holds" />
        )}
      </ChartCard>
    </div>
  )
}
