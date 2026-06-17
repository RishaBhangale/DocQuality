import {
  BarChart3,
  CheckCircle2,
  Clock,
  Zap,
  FileText,
  AlertCircle,
  Play,
  CheckCheck,
  Bell,
  Server,
} from 'lucide-react'
import {
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
} from 'recharts'
import { useMonitorAPI } from '../../hooks/useMonitorAPI'
import { KPICard } from '../shared/KPICard'
import { ChartCard } from '../shared/ChartCard'
import { CustomTooltip, RechartsTooltip } from '../shared/CustomTooltip'
import { LoadingState, ErrorState, EmptyState } from '../shared/StateDisplays'
import type {
  OverviewKPIs,
  WorkspaceSplit,
  ScoreTrend,
  FeedEvent,
  TimeRange,
  Workspace,
} from '../../types'
import { CHART_COLORS, EVENT_TYPE_COLORS } from '../../types'

interface OverviewTabProps {
  timeRange: TimeRange
  workspace: Workspace
  params: Record<string, string>
}

const EVENT_ICONS: Record<string, React.ReactNode> = {
  evaluation: <FileText size={14} />,
  error: <AlertCircle size={14} />,
  job_start: <Play size={14} />,
  job_complete: <CheckCheck size={14} />,
  alert: <Bell size={14} />,
  system: <Server size={14} />,
}

export function OverviewTab({ params }: OverviewTabProps) {
  const kpis = useMonitorAPI<OverviewKPIs>('/api/overview/kpis', params)
  const splits = useMonitorAPI<WorkspaceSplit[]>('/api/overview/workspace-split', params)
  const trends = useMonitorAPI<ScoreTrend[]>('/api/overview/score-trend', params)
  const feed = useMonitorAPI<FeedEvent[]>('/api/feed', params)

  if (kpis.loading && !kpis.data) return <LoadingState />
  if (kpis.error && !kpis.data) return <ErrorState message={kpis.error} onRetry={kpis.refetch} />

  const k = kpis.data

  return (
    <div className="space-y-6 animate-fade-in">
      {/* KPI Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <KPICard
          title="Total Evaluations"
          value={k?.total_evaluations ?? 0}
          format="number"
          subtitle="documents evaluated"
          trend="up"
          trendValue={k?.total_evaluations ? `${k.total_evaluations} docs` : 'no data'}
          icon={<BarChart3 size={18} />}
          accentColor="#2563EB"
          description="Total number of document evaluations completed within the selected time range and workspace filter. Each file submitted through the main POC counts as one evaluation."
        />
        <KPICard
          title="Success Rate"
          value={k?.success_rate ?? 0}
          format="percent"
          subtitle="pass threshold"
          trend={(k?.success_rate ?? 0) >= 80 ? 'up' : 'down'}
          trendValue={`${(k?.success_rate ?? 0).toFixed(1)}%`}
          icon={<CheckCircle2 size={18} />}
          accentColor="#16A34A"
          description="Percentage of jobs that completed successfully (status = 'completed'). Calculated as (completed_jobs ÷ total_jobs) × 100. A failed job is one that errored out during processing."
        />
        <KPICard
          title="Avg Score"
          value={k?.avg_score ?? 0}
          format="number"
          subtitle="across all metrics"
          trend="neutral"
          trendValue="stable"
          icon={<Zap size={18} />}
          accentColor="#D97706"
          description="Arithmetic mean of the overall_score field across all evaluations in the selected period. Score scale is 0–100 (or 0–1 for normalized metrics). Higher is better."
        />
        <KPICard
          title="Avg LLM Latency"
          value={k?.avg_llm_latency_ms ?? 0}
          format="ms"
          subtitle="per evaluation call"
          trend={(k?.avg_llm_latency_ms ?? 0) <= 2000 ? 'up' : 'down'}
          trendValue={(k?.avg_llm_latency_ms ?? 0) <= 2000 ? 'good' : 'slow'}
          icon={<Clock size={18} />}
          accentColor="#7C3AED"
          description="Average response time of all LLM API calls recorded during evaluations, across all pipeline steps. Includes domain scoring, sign-off checks, and regulatory mapping calls. Under 2s is considered healthy."
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Workspace split donut */}
        <ChartCard title="Workspace Distribution" subtitle="Evaluations by workspace">
          {splits.loading && !splits.data ? (
            <LoadingState />
          ) : splits.data?.length ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={splits.data}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={85}
                    dataKey="count"
                    nameKey="workspace"
                    strokeWidth={0}
                    paddingAngle={3}
                  >
                    {splits.data.map((_, i) => (
                      <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <RechartsTooltip content={<CustomTooltip />} />
                </PieChart>
              </ResponsiveContainer>
              {/* Legend */}
              <div className="flex items-center justify-center gap-4 -mt-2">
                {splits.data.map((s, i) => (
                  <div key={s.workspace} className="flex items-center gap-1.5 text-xs text-text-secondary">
                    <span
                      className="w-2.5 h-2.5 rounded-full"
                      style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
                    />
                    {s.workspace} ({s.count})
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <EmptyState />
          )}
        </ChartCard>

        {/* Score trend */}
        <ChartCard
          title="Score Trend"
          subtitle="Average score over time"
          className="lg:col-span-2"
        >
          {trends.loading && !trends.data ? (
            <LoadingState />
          ) : trends.data?.length ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trends.data}>
                  <defs>
                    <linearGradient id="scoreFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#2563EB" stopOpacity={0.2} />
                      <stop offset="100%" stopColor="#2563EB" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v: string) => v.slice(5)}
                  />
                  <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} tickFormatter={(v: number) => v.toFixed(1)} />
                  <RechartsTooltip content={<CustomTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="avg_score"
                    stroke="#2563EB"
                    strokeWidth={2}
                    fill="url(#scoreFill)"
                    name="Avg Score"
                    dot={false}
                    activeDot={{ r: 4, fill: '#2563EB' }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState />
          )}
        </ChartCard>
      </div>

      {/* Activity Feed & Active Jobs */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ChartCard
          title="Activity Feed"
          subtitle="Recent events"
          className="lg:col-span-2"
        >
          {feed.loading && !feed.data ? (
            <LoadingState />
          ) : feed.data?.length ? (
            <div className="space-y-1 max-h-72 overflow-y-auto pr-1">
              {feed.data.slice(0, 20).map((event, idx) => (
                <div
                  key={event.id}
                  className="flex items-start gap-3 px-3 py-2.5 rounded-xl hover:bg-slate-50 transition-colors animate-slide-in"
                  style={{ animationDelay: `${idx * 30}ms` }}
                >
                  <span
                    className="mt-0.5 p-1.5 rounded-lg shrink-0"
                    style={{
                      color: EVENT_TYPE_COLORS[event.event_type] ?? '#94A3B8',
                      backgroundColor: `${EVENT_TYPE_COLORS[event.event_type] ?? '#94A3B8'}18`,
                    }}
                  >
                    {EVENT_ICONS[event.event_type] ?? <FileText size={14} />}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-text-primary text-xs leading-relaxed truncate">
                      {event.message}
                    </p>
                    <p className="text-text-muted text-[10px] mt-0.5">
                      {new Date(event.timestamp).toLocaleString()}
                      {event.workspace && (
                        <span className="ml-2 px-1.5 py-0.5 rounded-md bg-slate-100 text-text-muted">
                          {event.workspace}
                        </span>
                      )}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState message="No recent events" />
          )}
        </ChartCard>

        {/* Active jobs */}
        <ChartCard title="System Status" subtitle="Active jobs & pipeline">
          <div className="flex flex-col items-center justify-center h-48 gap-4">
            <div className="relative">
              <div className="w-20 h-20 rounded-full border-4 border-accent-cyan/20 flex items-center justify-center">
                <span className="text-2xl font-bold text-accent-cyan">
                  {k?.active_jobs ?? 0}
                </span>
              </div>
              {(k?.active_jobs ?? 0) > 0 && (
                <div className="absolute inset-0 w-20 h-20 rounded-full animate-pulse-glow" />
              )}
            </div>
            <div className="text-center">
              <p className="text-text-secondary text-sm font-medium">Active Jobs</p>
              <p className="text-text-muted text-xs mt-0.5">
                {(k?.active_jobs ?? 0) === 0 ? 'Pipeline idle' : 'Processing…'}
              </p>
            </div>
          </div>
        </ChartCard>
      </div>
    </div>
  )
}
