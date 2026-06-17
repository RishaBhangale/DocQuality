import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
} from 'recharts'
import { useMonitorAPI } from '../../hooks/useMonitorAPI'
import { ChartCard } from '../shared/ChartCard'
import { CustomTooltip, RechartsTooltip } from '../shared/CustomTooltip'
import { LoadingState, ErrorState, EmptyState } from '../shared/StateDisplays'
import type {
  ScoreDistribution,
  WorkspaceScore,
  DomainScore,
  LowestDocument,
  TimeRange,
  Workspace,
} from '../../types'
import { CHART_COLORS } from '../../types'
import { FileWarning } from 'lucide-react'

interface EvaluationAnalyticsTabProps {
  timeRange: TimeRange
  workspace: Workspace
  params: Record<string, string>
}

export function EvaluationAnalyticsTab({ params }: EvaluationAnalyticsTabProps) {
  const distribution = useMonitorAPI<ScoreDistribution[]>('/api/evaluations/distribution', params)
  const byWorkspace = useMonitorAPI<WorkspaceScore[]>('/api/evaluations/by-workspace', params)
  const byDomain = useMonitorAPI<DomainScore[]>('/api/evaluations/by-domain', params)
  const lowest = useMonitorAPI<LowestDocument[]>('/api/evaluations/lowest', params)

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Top row: Distribution + By Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Score Distribution */}
        <ChartCard title="Score Distribution" subtitle="Histogram of evaluation scores">
          {distribution.loading && !distribution.data ? (
            <LoadingState />
          ) : distribution.error ? (
            <ErrorState message={distribution.error} onRetry={distribution.refetch} />
          ) : distribution.data?.length ? (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={distribution.data} barCategoryGap="15%">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <RechartsTooltip content={<CustomTooltip />} />
                  <Bar
                    dataKey="count"
                    name="Documents"
                    radius={[6, 6, 0, 0]}
                    fill="#2563EB"
                    fillOpacity={0.85}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState />
          )}
        </ChartCard>

        {/* Score by Workspace */}
        <ChartCard title="Score by Workspace" subtitle="Average and median scores per workspace">
          {byWorkspace.loading && !byWorkspace.data ? (
            <LoadingState />
          ) : byWorkspace.error ? (
            <ErrorState message={byWorkspace.error} onRetry={byWorkspace.refetch} />
          ) : byWorkspace.data?.length ? (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={byWorkspace.data} barCategoryGap="25%">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="workspace" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} tickFormatter={(v: number) => v.toFixed(1)} />
                  <RechartsTooltip content={<CustomTooltip />} />
                  <Bar
                    dataKey="avg_score"
                    name="Average"
                    radius={[6, 6, 0, 0]}
                    fill={CHART_COLORS[0]}
                    fillOpacity={0.85}
                  />
                  <Bar
                    dataKey="median_score"
                    name="Median"
                    radius={[6, 6, 0, 0]}
                    fill={CHART_COLORS[1]}
                    fillOpacity={0.85}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState />
          )}
        </ChartCard>
      </div>

      {/* Second row: Domain chart + lowest table */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Banking Domain */}
        <ChartCard title="Banking Domain Analysis" subtitle="Average score by banking sub-domain">
          {byDomain.loading && !byDomain.data ? (
            <LoadingState />
          ) : byDomain.error ? (
            <ErrorState message={byDomain.error} onRetry={byDomain.refetch} />
          ) : byDomain.data?.length ? (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={byDomain.data} layout="vertical" barCategoryGap="20%">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" domain={[0, 1]} tick={{ fontSize: 11 }} tickFormatter={(v: number) => v.toFixed(1)} />
                  <YAxis
                    type="category"
                    dataKey="domain"
                    width={100}
                    tick={{ fontSize: 11 }}
                  />
                  <RechartsTooltip content={<CustomTooltip />} />
                  <Bar
                    dataKey="avg_score"
                    name="Avg Score"
                    radius={[0, 6, 6, 0]}
                    fill={CHART_COLORS[2]}
                    fillOpacity={0.85}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState />
          )}
        </ChartCard>

        {/* Lowest scoring documents */}
        <ChartCard title="Lowest Scoring Documents" subtitle="Documents needing attention">
          {lowest.loading && !lowest.data ? (
            <LoadingState />
          ) : lowest.error ? (
            <ErrorState message={lowest.error} onRetry={lowest.refetch} />
          ) : lowest.data?.length ? (
            <div className="max-h-72 overflow-y-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-text-muted border-b border-border-subtle">
                    <th className="text-left py-2.5 px-3 font-medium">Document</th>
                    <th className="text-left py-2.5 px-3 font-medium">Score</th>
                    <th className="text-left py-2.5 px-3 font-medium">Workspace</th>
                    <th className="text-left py-2.5 px-3 font-medium">Failing</th>
                  </tr>
                </thead>
                <tbody>
                  {lowest.data.slice(0, 10).map((doc) => (
                    <tr
                      key={doc.document_id}
                      className="border-b border-border-subtle/50 hover:bg-slate-50 transition-colors"
                    >
                      <td className="py-2.5 px-3 text-text-primary flex items-center gap-2">
                        <FileWarning size={12} className="text-accent-red shrink-0" />
                        <span className="truncate max-w-[140px]" title={doc.filename}>
                          {doc.filename}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        <span
                          className={`font-semibold ${
                            doc.score < 0.4
                              ? 'text-accent-red'
                              : doc.score < 0.7
                                ? 'text-accent-amber'
                                : 'text-accent-green'
                          }`}
                        >
                          {doc.score?.toFixed(2) ?? '—'}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-text-secondary">{doc.workspace}</td>
                      <td className="py-2.5 px-3">
                        <div className="flex flex-wrap gap-1">
                          {(doc.failing_metrics || []).slice(0, 2).map((m) => (
                            <span
                              key={m}
                              className="px-1.5 py-0.5 rounded-md bg-accent-red/10 text-accent-red text-[10px]"
                            >
                              {m}
                            </span>
                          ))}
                          {(doc.failing_metrics || []).length > 2 && (
                            <span className="text-text-muted text-[10px]">
                              +{(doc.failing_metrics || []).length - 2}
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState message="No low-scoring documents" />
          )}
        </ChartCard>
      </div>
    </div>
  )
}
