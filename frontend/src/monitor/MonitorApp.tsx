import { useState } from 'react'
import {
  LayoutDashboard,
  FileText,
  Cpu,
  Compass,
  ShieldAlert,
  GitFork,
  Download,
  ChevronDown,
  Activity,
} from 'lucide-react'
import { TimeRange, Workspace } from './types'
import { TimeRangePicker, getDateRange } from './components/shared/TimeRangePicker'
import { WorkspaceFilter } from './components/shared/WorkspaceFilter'

import { OverviewTab } from './components/tabs/OverviewTab'
import { EvaluationAnalyticsTab } from './components/tabs/EvaluationAnalyticsTab'
import { LLMPerformanceTab } from './components/tabs/LLMPerformanceTab'
import { MetricDeepDiveTab } from './components/tabs/MetricDeepDiveTab'
import { RegulatoryTab } from './components/tabs/RegulatoryTab'
import { PipelineSystemTab } from './components/tabs/PipelineSystemTab'
import { ErrorBoundary } from './components/shared/ErrorBoundary'

type TabType = 'overview' | 'evaluations' | 'llm' | 'metrics' | 'regulatory' | 'pipeline'

export function MonitorApp() {
  const [activeTab, setActiveTab] = useState<TabType>('overview')
  const [timeRange, setTimeRange] = useState<TimeRange>('7d')
  const [workspace, setWorkspace] = useState<Workspace>('all')
  const [exportOpen, setExportOpen] = useState(false)

  const dateRange = getDateRange(timeRange)
  const params: Record<string, string> = {
    workspace,
    from_date: dateRange.from_date,
    to_date: dateRange.to_date,
  }

  const handleExport = (section: string) => {
    const fromStr = dateRange.from_date ? `&from_date=${dateRange.from_date}` : ''
    const toStr = dateRange.to_date ? `&to_date=${dateRange.to_date}` : ''
    window.location.href = `/api/export/csv?section=${section}&workspace=${workspace}${fromStr}${toStr}`
    setExportOpen(false)
  }

  const tabs: { id: TabType; label: string; icon: React.ReactNode }[] = [
    { id: 'overview', label: 'Overview', icon: <LayoutDashboard size={16} /> },
    { id: 'evaluations', label: 'Evaluations', icon: <FileText size={16} /> },
    { id: 'llm', label: 'LLM Performance', icon: <Cpu size={16} /> },
    { id: 'metrics', label: 'Metrics Deep Dive', icon: <Compass size={16} /> },
    { id: 'regulatory', label: 'Regulatory', icon: <ShieldAlert size={16} /> },
    { id: 'pipeline', label: 'Pipeline & System', icon: <GitFork size={16} /> },
  ]

  return (
    <div className="min-h-screen bg-obsidian text-text-primary flex flex-col">
      {/* Header */}
      <header className="border-b border-border-subtle bg-white sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="p-2 rounded-xl bg-accent-cyan/10 text-accent-cyan">
              <Activity size={20} className="animate-pulse" />
            </span>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-text-primary flex items-center gap-2">
                DocQuality <span className="text-xs px-2 py-0.5 rounded-full bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/20">Observatory</span>
              </h1>
              <p className="text-[10px] text-text-secondary">Pipeline Metrics & Compliance Monitoring</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Filters */}
            <WorkspaceFilter value={workspace} onChange={setWorkspace} />
            <TimeRangePicker value={timeRange} onChange={setTimeRange} />

            {/* Export Dropdown */}
            <div className="relative">
              <button
                onClick={() => setExportOpen(!exportOpen)}
                className="flex items-center gap-2 px-3 py-1.5 bg-surface text-text-secondary hover:text-text-primary border border-border-subtle hover:border-text-secondary/30 rounded-xl text-xs font-medium transition-all"
              >
                <Download size={14} />
                <span>Export CSV</span>
                <ChevronDown size={12} className={`transition-transform duration-200 ${exportOpen ? 'rotate-180' : ''}`} />
              </button>

              {exportOpen && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setExportOpen(false)} />
                  <div className="absolute right-0 mt-2 w-48 bg-white border border-border-subtle rounded-xl shadow-lg z-20 py-1.5 overflow-hidden animate-fade-in animate-slide-in">
                    <div className="px-3 py-1.5 text-[10px] font-bold text-text-muted uppercase tracking-wider border-b border-border-subtle/40 mb-1">
                      Select Section to Export
                    </div>
                    <button
                      onClick={() => handleExport('overview')}
                      className="w-full text-left px-4 py-2 text-xs text-text-secondary hover:bg-slate-50 hover:text-text-primary transition-colors"
                    >
                      Overview Report
                    </button>
                    <button
                      onClick={() => handleExport('evaluations')}
                      className="w-full text-left px-4 py-2 text-xs text-text-secondary hover:bg-slate-50 hover:text-text-primary transition-colors"
                    >
                      Evaluation History
                    </button>
                    <button
                      onClick={() => handleExport('llm')}
                      className="w-full text-left px-4 py-2 text-xs text-text-secondary hover:bg-slate-50 hover:text-text-primary transition-colors"
                    >
                      LLM Performance
                    </button>
                    <button
                      onClick={() => handleExport('metrics')}
                      className="w-full text-left px-4 py-2 text-xs text-text-secondary hover:bg-slate-50 hover:text-text-primary transition-colors"
                    >
                      Metric Averages
                    </button>
                    <button
                      onClick={() => handleExport('regulatory')}
                      className="w-full text-left px-4 py-2 text-xs text-text-secondary hover:bg-slate-50 hover:text-text-primary transition-colors"
                    >
                      Regulatory Summary
                    </button>
                    <button
                      onClick={() => handleExport('pipeline')}
                      className="w-full text-left px-4 py-2 text-xs text-text-secondary hover:bg-slate-50 hover:text-text-primary transition-colors"
                    >
                      Pipeline Step Timings
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <div className="border-b border-border-subtle bg-white/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <nav className="flex space-x-1 py-3 overflow-x-auto scrollbar-none" aria-label="Tabs">
            {tabs.map((tab) => {
              const active = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`
                    flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-xl transition-all duration-200 shrink-0
                    ${active
                      ? 'bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/25'
                      : 'text-text-secondary hover:text-text-primary hover:bg-surface border border-transparent'
                    }
                  `}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              )
            })}
          </nav>
        </div>
      </div>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activeTab === 'overview' && (
          <ErrorBoundary tabName="Overview">
            <OverviewTab timeRange={timeRange} workspace={workspace} params={params} />
          </ErrorBoundary>
        )}
        {activeTab === 'evaluations' && (
          <ErrorBoundary tabName="Evaluations">
            <EvaluationAnalyticsTab timeRange={timeRange} workspace={workspace} params={params} />
          </ErrorBoundary>
        )}
        {activeTab === 'llm' && (
          <ErrorBoundary tabName="LLM Performance">
            <LLMPerformanceTab timeRange={timeRange} workspace={workspace} params={params} />
          </ErrorBoundary>
        )}
        {activeTab === 'metrics' && (
          <ErrorBoundary tabName="Metrics Deep Dive">
            <MetricDeepDiveTab timeRange={timeRange} workspace={workspace} params={params} />
          </ErrorBoundary>
        )}
        {activeTab === 'regulatory' && (
          <ErrorBoundary tabName="Regulatory">
            <RegulatoryTab timeRange={timeRange} workspace={workspace} params={params} />
          </ErrorBoundary>
        )}
        {activeTab === 'pipeline' && (
          <ErrorBoundary tabName="Pipeline & System">
            <PipelineSystemTab timeRange={timeRange} workspace={workspace} params={params} />
          </ErrorBoundary>
        )}
      </main>
    </div>
  )
}
