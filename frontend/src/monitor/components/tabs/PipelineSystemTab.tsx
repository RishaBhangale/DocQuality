import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
} from 'recharts'
import {
  Activity,
  HardDrive,
  Cpu,
  MemoryStick,
  Server,
  Layers,
  CheckCircle2,
  XCircle,
  Clock,
} from 'lucide-react'
import { useMonitorAPI } from '../../hooks/useMonitorAPI'
import { ChartCard } from '../shared/ChartCard'
import { CustomTooltip, RechartsTooltip } from '../shared/CustomTooltip'
import { LoadingState, ErrorState, EmptyState } from '../shared/StateDisplays'
import type {
  StepTiming,
  PipelineSuccessRate,
  QueueDepth,
  SystemHealth,
  DocumentType,
  TimeRange,
  Workspace,
} from '../../types'
import { CHART_COLORS } from '../../types'

interface PipelineSystemTabProps {
  timeRange: TimeRange
  workspace: Workspace
  params: Record<string, string>
}

const STATUS_COLORS: Record<string, string> = {
  completed: '#16A34A',
  failed: '#DC2626',
  pending: '#D97706',
  processing: '#2563EB',
  cancelled: '#9CA3AF',
}

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (d > 0) return `${d}d ${h}h`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

export function PipelineSystemTab({ params }: PipelineSystemTabProps) {
  const stepTimings = useMonitorAPI<StepTiming[]>('/api/pipeline/step-timings', params)
  const successRate = useMonitorAPI<PipelineSuccessRate[]>('/api/pipeline/success-rate', params)
  const queueDepth = useMonitorAPI<QueueDepth[]>('/api/pipeline/queue-depth', params)
  const health = useMonitorAPI<SystemHealth>('/api/system/health', params)
  const docTypes = useMonitorAPI<DocumentType[]>('/api/documents/types', params)

  const h = health.data

  return (
    <div className="space-y-6 animate-fade-in">
      {/* System Health Banner */}
      <div className="glass-card rounded-2xl p-5">
        {health.loading && !h ? (
          <LoadingState message="Checking system health…" />
        ) : health.error ? (
          <ErrorState message={health.error} onRetry={health.refetch} />
        ) : h ? (
          <div className="flex flex-col lg:flex-row items-start lg:items-center gap-6">
            {/* Status badge */}
            <div className="flex items-center gap-3">
              <div
                className={`w-3 h-3 rounded-full ${
                  h.status === 'healthy'
                    ? 'bg-accent-green animate-pulse'
                    : h.status === 'degraded'
                      ? 'bg-accent-amber animate-pulse'
                      : 'bg-accent-red'
                }`}
              />
              <span className="text-text-primary text-sm font-semibold capitalize">
                System {h.status}
              </span>
              <span className="text-text-muted text-xs">
                Last checked {new Date(h.last_check).toLocaleTimeString()}
              </span>
            </div>

            {/* Metrics row */}
            <div className="flex flex-wrap items-center gap-6 lg:ml-auto">
              <div className="flex items-center gap-2 text-xs">
                <Clock size={14} className="text-accent-cyan" />
                <span className="text-text-secondary">Uptime:</span>
                <span className="text-text-primary font-medium">{formatUptime(h.uptime_seconds || 0)}</span>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <Cpu size={14} className="text-accent-purple" />
                <span className="text-text-secondary">CPU:</span>
                <span className={`font-medium ${(h.cpu_percent || 0) > 80 ? 'text-accent-red' : 'text-text-primary'}`}>
                  {(h.cpu_percent || 0).toFixed(1)}%
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <MemoryStick size={14} className="text-accent-amber" />
                <span className="text-text-secondary">Memory:</span>
                <span className={`font-medium ${(h.memory_percent || 0) > 85 ? 'text-accent-red' : 'text-text-primary'}`}>
                  {(h.memory_percent || 0).toFixed(1)}%
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <HardDrive size={14} className="text-accent-green" />
                <span className="text-text-secondary">Disk:</span>
                <span className={`font-medium ${(h.disk_percent || 0) > 90 ? 'text-accent-red' : 'text-text-primary'}`}>
                  {(h.disk_percent || 0).toFixed(1)}%
                </span>
              </div>
            </div>
          </div>
        ) : (
          <EmptyState />
        )}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Pipeline Step Timings */}
        <ChartCard
          title="Pipeline Step Timings"
          subtitle="Average duration per processing step"
          className="lg:col-span-2"
        >
          {stepTimings.loading && !stepTimings.data ? (
            <LoadingState />
          ) : stepTimings.error ? (
            <ErrorState message={stepTimings.error} onRetry={stepTimings.refetch} />
          ) : stepTimings.data?.length ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={stepTimings.data} barCategoryGap="20%">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="step" tick={{ fontSize: 10 }} angle={-15} textAnchor="end" height={50} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => `${v}ms`} />
                  <RechartsTooltip content={<CustomTooltip />} />
                  <Bar
                    dataKey="avg_duration_ms"
                    name="Avg (ms)"
                    radius={[6, 6, 0, 0]}
                    fill={CHART_COLORS[0]}
                    fillOpacity={0.85}
                  />
                  <Bar
                    dataKey="max_duration_ms"
                    name="Max (ms)"
                    radius={[6, 6, 0, 0]}
                    fill={CHART_COLORS[4]}
                    fillOpacity={0.4}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState />
          )}
        </ChartCard>

        {/* Job Status Pie */}
        <ChartCard title="Job Status" subtitle="Distribution of pipeline job outcomes">
          {successRate.loading && !successRate.data ? (
            <LoadingState />
          ) : successRate.error ? (
            <ErrorState message={successRate.error} onRetry={successRate.refetch} />
          ) : successRate.data?.length ? (
            <div className="h-64 flex flex-col items-center">
              <ResponsiveContainer width="100%" height="80%">
                <PieChart>
                  <Pie
                    data={successRate.data}
                    cx="50%"
                    cy="50%"
                    innerRadius={40}
                    outerRadius={70}
                    dataKey="count"
                    nameKey="status"
                    strokeWidth={0}
                    paddingAngle={2}
                  >
                    {successRate.data.map((entry) => (
                      <Cell
                        key={entry.status}
                        fill={STATUS_COLORS[entry.status] ?? '#94A3B8'}
                      />
                    ))}
                  </Pie>
                  <RechartsTooltip content={<CustomTooltip />} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex flex-wrap items-center justify-center gap-3 -mt-1">
                {successRate.data.map((s) => (
                  <div key={s.status} className="flex items-center gap-1.5 text-[10px] text-text-secondary">
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: STATUS_COLORS[s.status] ?? '#94A3B8' }}
                    />
                    {s.status} ({s.count})
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <EmptyState />
          )}
        </ChartCard>
      </div>

      {/* Bottom row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Queue Depth */}
        <ChartCard title="Queue Depth" subtitle="Current processing queue status">
          {queueDepth.loading && !queueDepth.data ? (
            <LoadingState />
          ) : queueDepth.error ? (
            <ErrorState message={queueDepth.error} onRetry={queueDepth.refetch} />
          ) : queueDepth.data?.length ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 py-2">
              {queueDepth.data.map((q) => (
                <div
                  key={q.queue_name}
                  className="bg-slate-50 rounded-xl p-4 border border-border-subtle"
                >
                  <div className="flex items-center gap-2 mb-3">
                    <Layers size={14} className="text-accent-cyan" />
                    <span className="text-text-primary text-xs font-medium">
                      {q.queue_name}
                    </span>
                  </div>
                  <div className="flex items-end gap-4">
                    <div>
                      <p className="text-2xl font-bold text-text-primary">{q.depth}</p>
                      <p className="text-[10px] text-text-muted">queued</p>
                    </div>
                    <div>
                      <p className="text-lg font-semibold text-accent-cyan">{q.processing}</p>
                      <p className="text-[10px] text-text-muted">processing</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState message="No active queues" />
          )}
        </ChartCard>

        {/* Document Types */}
        <ChartCard title="Document Types" subtitle="Distribution of processed document formats">
          {docTypes.loading && !docTypes.data ? (
            <LoadingState />
          ) : docTypes.error ? (
            <ErrorState message={docTypes.error} onRetry={docTypes.refetch} />
          ) : docTypes.data?.length ? (
            <div className="space-y-2.5 py-2">
              {docTypes.data.map((dt, idx) => (
                <div key={dt.doc_type} className="flex items-center gap-3">
                  <span className="text-text-secondary text-xs w-16 truncate font-medium">
                    {dt.doc_type}
                  </span>
                  <div className="flex-1 h-3 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{
                        width: `${dt.percentage}%`,
                        backgroundColor: CHART_COLORS[idx % CHART_COLORS.length],
                      }}
                    />
                  </div>
                  <span className="text-text-muted text-xs w-12 text-right">
                    {dt.count}
                  </span>
                  <span className="text-text-muted text-[10px] w-10 text-right">
                    {dt.percentage.toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState />
          )}
        </ChartCard>
      </div>
    </div>
  )
}
