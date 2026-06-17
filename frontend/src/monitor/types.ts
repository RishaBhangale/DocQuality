/* ────────────────────────────────────────────────────────────
   DocQuality Monitor — shared TypeScript types
   ──────────────────────────────────────────────────────────── */

// ── Generic API wrapper ──
export interface APIResponse<T> {
  data: T | null
  loading: boolean
  error: string | null
  refetch: () => void
}

// ── Time range ──
export type TimeRange = '7d' | '30d' | '90d' | 'all'
export type Workspace = 'all' | 'banking' | 'compliance'

// ── Overview ──
export interface OverviewKPIs {
  total_evaluations: number
  success_rate: number
  avg_score: number
  avg_llm_latency_ms: number
  active_jobs: number
}

export interface WorkspaceSplit {
  workspace: string
  count: number
  avg_score: number
}

export interface ScoreTrend {
  date: string
  avg_score: number
  count: number
}

export interface FeedEvent {
  id: string
  timestamp: string
  event_type: 'evaluation' | 'error' | 'job_start' | 'job_complete' | 'alert' | 'system'
  message: string
  severity: 'info' | 'warning' | 'error' | 'success'
  workspace?: string
}

// ── Evaluations ──
export interface ScoreDistribution {
  bucket: string
  count: number
}

export interface WorkspaceScore {
  workspace: string
  avg_score: number
  median_score: number
  count: number
}

export interface DomainScore {
  domain: string
  avg_score: number
  count: number
}

export interface LowestDocument {
  document_id: string
  filename: string
  score: number
  workspace: string
  evaluated_at: string
  failing_metrics: string[]
}

// ── LLM Performance ──
export interface LLMKPIs {
  total_calls: number
  error_rate: number
  avg_latency_ms: number
  estimated_cost_usd: number
}

export interface StepLatency {
  step: string
  avg_latency_ms: number
  p95_latency_ms: number
  call_count: number
}

export interface TokenUsage {
  date: string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

export interface LLMError {
  id: string
  timestamp: string
  step: string
  error_type: string
  message: string
  model: string
}

// ── Metrics ──
export interface MetricAverage {
  metric: string
  avg_score: number
  min_score: number
  max_score: number
  evaluation_count: number
  type: 'deterministic' | 'llm'
}

export interface DetVsLLM {
  metric: string
  deterministic_score: number
  llm_score: number
}

// ── Regulatory ──
export interface ComplianceRate {
  overall_rate: number
  total_evaluated: number
  total_passing: number
  total_failing: number
}

export interface ThresholdFailure {
  metric: string
  failure_count: number
  threshold: number
  avg_score: number
}

export interface LegalHold {
  id: string
  document_id: string
  filename: string
  reason: string
  created_at: string
  status: 'active' | 'released'
}

export interface IssueSummary {
  severity: 'critical' | 'high' | 'medium' | 'low'
  count: number
}

// ── Pipeline & System ──
export interface StepTiming {
  step: string
  avg_duration_ms: number
  min_duration_ms: number
  max_duration_ms: number
}

export interface PipelineSuccessRate {
  status: string
  count: number
}

export interface QueueDepth {
  queue_name: string
  depth: number
  processing: number
}

export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'down'
  uptime_seconds: number
  cpu_percent: number
  memory_percent: number
  disk_percent: number
  last_check: string
}

export interface DocumentType {
  doc_type: string
  count: number
  percentage: number
}

// ── Chart palette ──
export const CHART_COLORS = [
  '#2563EB', // blue
  '#7C3AED', // violet
  '#D97706', // amber
  '#16A34A', // green
  '#DC2626', // red
  '#DB2777', // pink
] as const

export const SEVERITY_COLORS: Record<string, string> = {
  critical: '#DC2626',
  high: '#D97706',
  medium: '#2563EB',
  low: '#16A34A',
}

export const EVENT_TYPE_COLORS: Record<string, string> = {
  evaluation: '#2563EB',
  error: '#DC2626',
  job_start: '#7C3AED',
  job_complete: '#16A34A',
  alert: '#D97706',
  system: '#6B7280',
}
