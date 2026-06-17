import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { useMonitorAPI } from '../../hooks/useMonitorAPI'
import { ChartCard } from '../shared/ChartCard'
import { CustomTooltip, RechartsTooltip } from '../shared/CustomTooltip'
import { LoadingState, ErrorState, EmptyState } from '../shared/StateDisplays'
import type {
  MetricAverage,
  DetVsLLM,
  TimeRange,
  Workspace,
} from '../../types'
import { CHART_COLORS } from '../../types'
import { AlertTriangle } from 'lucide-react'

interface MetricDeepDiveTabProps {
  timeRange: TimeRange
  workspace: Workspace
  params: Record<string, string>
}

export function MetricDeepDiveTab({ params }: MetricDeepDiveTabProps) {
  const averages = useMonitorAPI<MetricAverage[]>('/api/metrics/averages', params)
  const detVsLlm = useMonitorAPI<DetVsLLM[]>('/api/metrics/det-vs-llm', params)

  // Derive worst metrics
  const worstMetrics = averages.data
    ? [...averages.data].sort((a, b) => a.avg_score - b.avg_score).slice(0, 6)
    : []

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Radar chart */}
        <ChartCard title="Metric Averages" subtitle="Radar view of all quality metrics">
          {averages.loading && !averages.data ? (
            <LoadingState />
          ) : averages.error ? (
            <ErrorState message={averages.error} onRetry={averages.refetch} />
          ) : averages.data?.length ? (
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart
                  data={averages.data}
                  cx="50%"
                  cy="50%"
                  outerRadius="70%"
                >
                  <PolarGrid
                    stroke="#E2E8F0"
                    gridType="polygon"
                  />
                  <PolarAngleAxis
                    dataKey="metric"
                    tick={{ fontSize: 10, fill: '#374151' }}
                  />
                  <PolarRadiusAxis
                    angle={30}
                    domain={[0, 1]}
                    tick={{ fontSize: 10, fill: '#64748B' }}
                    tickFormatter={(v: number) => v.toFixed(1)}
                  />
                  <Radar
                    name="Average Score"
                    dataKey="avg_score"
                    stroke={CHART_COLORS[0]}
                    fill={CHART_COLORS[0]}
                    fillOpacity={0.2}
                    strokeWidth={2}
                  />
                  <RechartsTooltip content={<CustomTooltip />} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState />
          )}
        </ChartCard>

        {/* Worst performing metrics */}
        <ChartCard title="Worst Performing Metrics" subtitle="Metrics with lowest average scores">
          {averages.loading && !averages.data ? (
            <LoadingState />
          ) : worstMetrics.length ? (
            <div className="space-y-3 py-2">
              {worstMetrics.map((m, idx) => {
                const pct = m.avg_score * 100
                const barColor =
                  pct < 40 ? '#EF4444' : pct < 70 ? '#F59E0B' : '#22C55E'

                return (
                  <div
                    key={m.metric}
                    className="animate-slide-in"
                    style={{ animationDelay: `${idx * 60}ms` }}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        {pct < 40 && (
                          <AlertTriangle size={12} className="text-accent-red" />
                        )}
                        <span className="text-text-primary text-xs font-medium">
                          {m.metric}
                        </span>
                        <span
                          className={`text-[10px] px-1.5 py-0.5 rounded-md ${
                            m.type === 'llm'
                              ? 'bg-accent-purple/10 text-accent-purple'
                              : 'bg-accent-cyan/10 text-accent-cyan'
                          }`}
                        >
                          {m.type}
                        </span>
                      </div>
                      <span className="text-text-secondary text-xs font-semibold">
                        {m.avg_score.toFixed(3)}
                      </span>
                    </div>
                    <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-700"
                        style={{
                          width: `${pct}%`,
                          backgroundColor: barColor,
                        }}
                      />
                    </div>
                    <div className="flex items-center justify-between mt-0.5 text-[10px] text-text-muted">
                      <span>Min: {m.min_score.toFixed(2)}</span>
                      <span>Max: {m.max_score.toFixed(2)}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <EmptyState />
          )}
        </ChartCard>
      </div>

      {/* Det vs LLM */}
      <ChartCard
        title="Deterministic vs LLM Metrics"
        subtitle="Side-by-side comparison of deterministic and LLM-based scoring"
      >
        {detVsLlm.loading && !detVsLlm.data ? (
          <LoadingState />
        ) : detVsLlm.error ? (
          <ErrorState message={detVsLlm.error} onRetry={detVsLlm.refetch} />
        ) : detVsLlm.data?.length ? (
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={detVsLlm.data} barCategoryGap="25%">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="metric" tick={{ fontSize: 10 }} angle={-15} textAnchor="end" height={50} />
                <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} tickFormatter={(v: number) => v.toFixed(1)} />
                <RechartsTooltip content={<CustomTooltip />} />
                <Legend
                  wrapperStyle={{ fontSize: 11, color: '#374151' }}
                />
                <Bar
                  dataKey="deterministic_score"
                  name="Deterministic"
                  radius={[6, 6, 0, 0]}
                  fill={CHART_COLORS[0]}
                  fillOpacity={0.85}
                />
                <Bar
                  dataKey="llm_score"
                  name="LLM"
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
  )
}
