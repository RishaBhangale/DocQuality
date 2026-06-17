import {
  Phone,
  AlertTriangle,
  Clock,
  DollarSign,
} from 'lucide-react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  AreaChart,
  Area,
  ResponsiveContainer,
} from 'recharts'
import { useMonitorAPI } from '../../hooks/useMonitorAPI'
import { KPICard } from '../shared/KPICard'
import { ChartCard } from '../shared/ChartCard'
import { CustomTooltip, RechartsTooltip } from '../shared/CustomTooltip'
import { LoadingState, ErrorState, EmptyState } from '../shared/StateDisplays'
import type {
  LLMKPIs,
  StepLatency,
  TokenUsage,
  LLMError,
  TimeRange,
  Workspace,
} from '../../types'
import { CHART_COLORS } from '../../types'

interface LLMPerformanceTabProps {
  timeRange: TimeRange
  workspace: Workspace
  params: Record<string, string>
}

export function LLMPerformanceTab({ params }: LLMPerformanceTabProps) {
  const kpis = useMonitorAPI<LLMKPIs>('/api/llm/kpis', params)
  const byStep = useMonitorAPI<StepLatency[]>('/api/llm/by-step', params)
  const tokens = useMonitorAPI<TokenUsage[]>('/api/llm/token-usage', params)
  const errors = useMonitorAPI<LLMError[]>('/api/llm/errors', params)

  const k = kpis.data

  return (
    <div className="space-y-6 animate-fade-in">
      {/* KPI Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <KPICard
          title="Total LLM Calls"
          value={k?.total_calls ?? 0}
          format="number"
          subtitle="API invocations"
          icon={<Phone size={18} />}
          accentColor="#2563EB"
          description="Total number of LLM API calls made across all evaluation pipeline steps. Includes domain scoring, sign-off analysis, regulatory mapping, and deterministic-LLM blending steps. Each document evaluation typically triggers 3–6 LLM calls."
        />
        <KPICard
          title="Error Rate"
          value={k?.error_rate ?? 0}
          format="percent"
          subtitle="of all calls"
          trend={(k?.error_rate ?? 0) <= 2 ? 'up' : 'down'}
          trendValue={(k?.error_rate ?? 0) <= 2 ? 'healthy' : 'elevated'}
          icon={<AlertTriangle size={18} />}
          accentColor="#DC2626"
          description="Percentage of LLM API calls that returned an error status (HTTP ≥ 4xx, timeout, or exception). Calculated as (error_count ÷ total_calls) × 100. Under 2% is considered healthy; above 5% indicates systemic issues."
        />
        <KPICard
          title="Avg Latency"
          value={k?.avg_latency_ms ?? 0}
          format="ms"
          subtitle="response time"
          icon={<Clock size={18} />}
          accentColor="#D97706"
          description="Mean wall-clock time from sending the LLM request to receiving the full response, across all successful calls in the period. Slow latency (>3s) directly increases per-document evaluation time."
        />
        <KPICard
          title="Est. Cost"
          value={k?.estimated_cost_usd ?? 0}
          format="currency"
          subtitle="USD this period"
          icon={<DollarSign size={18} />}
          accentColor="#16A34A"
          description="Estimated LLM API cost using GPT-4o pricing: $2.50 per 1M input tokens and $10.00 per 1M output tokens. Formula: (total_input_tokens ÷ 1,000,000 × $2.50) + (total_output_tokens ÷ 1,000,000 × $10.00)."
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Latency by Step */}
        <ChartCard title="Latency by Step" subtitle="Average and P95 latency per pipeline step">
          {byStep.loading && !byStep.data ? (
            <LoadingState />
          ) : byStep.error ? (
            <ErrorState message={byStep.error} onRetry={byStep.refetch} />
          ) : byStep.data?.length ? (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={byStep.data} barCategoryGap="20%">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="step" tick={{ fontSize: 10 }} angle={-20} textAnchor="end" height={50} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => `${v}ms`} />
                  <RechartsTooltip content={<CustomTooltip />} />
                  <Bar
                    dataKey="avg_latency_ms"
                    name="Avg (ms)"
                    radius={[6, 6, 0, 0]}
                    fill={CHART_COLORS[0]}
                    fillOpacity={0.85}
                  />
                  <Bar
                    dataKey="p95_latency_ms"
                    name="P95 (ms)"
                    radius={[6, 6, 0, 0]}
                    fill={CHART_COLORS[1]}
                    fillOpacity={0.6}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState />
          )}
        </ChartCard>

        {/* Token Usage */}
        <ChartCard title="Token Consumption" subtitle="Prompt vs completion tokens over time">
          {tokens.loading && !tokens.data ? (
            <LoadingState />
          ) : tokens.error ? (
            <ErrorState message={tokens.error} onRetry={tokens.refetch} />
          ) : tokens.data?.length ? (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={tokens.data}>
                  <defs>
                    <linearGradient id="promptFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={CHART_COLORS[0]} stopOpacity={0.3} />
                      <stop offset="100%" stopColor={CHART_COLORS[0]} stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="completionFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={CHART_COLORS[1]} stopOpacity={0.3} />
                      <stop offset="100%" stopColor={CHART_COLORS[1]} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v: string) => v.slice(5)}
                  />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) =>
                    v >= 1000 ? `${(v/1000).toFixed(0)}k` : `${v}`
                  } />
                  <RechartsTooltip content={<CustomTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="prompt_tokens"
                    stackId="1"
                    stroke={CHART_COLORS[0]}
                    strokeWidth={2}
                    fill="url(#promptFill)"
                    name="Prompt Tokens"
                  />
                  <Area
                    type="monotone"
                    dataKey="completion_tokens"
                    stackId="1"
                    stroke={CHART_COLORS[1]}
                    strokeWidth={2}
                    fill="url(#completionFill)"
                    name="Completion Tokens"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState />
          )}
        </ChartCard>
      </div>

      {/* Error Table */}
      <ChartCard title="LLM Errors" subtitle="Recent error events">
        {errors.loading && !errors.data ? (
          <LoadingState />
        ) : errors.error ? (
          <ErrorState message={errors.error} onRetry={errors.refetch} />
        ) : errors.data?.length ? (
          <div className="max-h-72 overflow-y-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-text-muted border-b border-border-subtle">
                  <th className="text-left py-2.5 px-3 font-medium">Timestamp</th>
                  <th className="text-left py-2.5 px-3 font-medium">Step</th>
                  <th className="text-left py-2.5 px-3 font-medium">Type</th>
                  <th className="text-left py-2.5 px-3 font-medium">Message</th>
                  <th className="text-left py-2.5 px-3 font-medium">Model</th>
                </tr>
              </thead>
              <tbody>
                {errors.data.slice(0, 15).map((err) => (
                  <tr
                    key={err.id}
                    className="border-b border-border-subtle/50 hover:bg-slate-50 transition-colors"
                  >
                    <td className="py-2.5 px-3 text-text-muted whitespace-nowrap">
                      {new Date(err.timestamp).toLocaleString()}
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="px-2 py-0.5 rounded-md bg-accent-purple/10 text-accent-purple">
                        {err.step}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-accent-red font-medium">{err.error_type}</td>
                    <td className="py-2.5 px-3 text-text-secondary truncate max-w-[240px]" title={err.message}>
                      {err.message}
                    </td>
                    <td className="py-2.5 px-3 text-text-muted">{err.model}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState message="No errors — looking good!" />
        )}
      </ChartCard>
    </div>
  )
}
