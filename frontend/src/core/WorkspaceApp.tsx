import { useState, useEffect } from 'react';
import { UploadCard } from './components/UploadCard';
import { ScoreCircle } from './components/ScoreCircle';
import { ExecutiveSummary } from './components/ExecutiveSummary';
import { MetricCard } from './components/MetricCard';
import { IssuesTable } from './components/IssuesTable';
import { HistoryModal } from './components/HistoryModal';
import { MetricRadarChart } from './components/MetricRadarChart';
import { MetricBarChart } from './components/MetricBarChart';
import { StatusBadge } from './components/StatusBadge';
import { AlertBox } from './components/AlertBox';
import { QualityDimensionsRow } from './components/QualityDimensionsRow';
import { ChevronLeft, Database, Download } from 'lucide-react';
import { KnowledgeBasePanel } from '../shared/KnowledgeBasePanel';

import { BankingMetricCard } from '../banking/components/BankingMetricCard';

export interface WorkspaceConfig {
  workspace: 'banking' | 'compliance';
  title: string;
  subtitle: string;
  theme: { primary: string; accent: string; gradient: string; chartStroke?: string };
  apiBaseUrl: string;
  hasDomainMetrics: boolean;
  hasLegalHold: boolean;
  hasRemediation: boolean;
  hasPdfReport: boolean;
  hasLinkedStandards: boolean;
  /** Pill next to "Standards-Specific Metrics" (compliance). */
  standardsSectionBadge?: string;
  /** Third chart column (severity). Default true; set false for compact compliance layout. */
  analyticsShowSeverityPie?: boolean;
  /** Optional centered footer under results. */
  footerTagline?: string;
}

function deriveCoreAndTypeMetrics(results: Record<string, any>) {
  let core: any[] = Array.isArray(results.core_metrics) && results.core_metrics.length
    ? results.core_metrics
    : (results.metrics || []).filter((m: any) => (m.category || 'core') === 'core');
  let typeSpecific: any[] = Array.isArray(results.type_specific_metrics) && results.type_specific_metrics.length
    ? results.type_specific_metrics
    : (results.metrics || []).filter((m: any) => m.category === 'type_specific');
  if (!core.length && !typeSpecific.length && Array.isArray(results.metrics) && results.metrics.length) {
    core = results.metrics;
  }
  return { coreMetrics: core, typeMetrics: typeSpecific };
}

function averageScores(metrics: { score: number }[]): number {
  if (!metrics.length) return 0;
  return metrics.reduce((a, m) => a + (Number(m.score) || 0), 0) / metrics.length;
}

function normalizeChartsPayload(raw: any) {
  if (!raw || typeof raw !== 'object') return raw;
  const normalized = { ...raw } as any;

  if (!normalized.radarData && raw.radar?.labels && raw.radar?.datasets?.[0]?.data) {
    normalized.radarData = raw.radar.labels.map((label: string, index: number) => ({
      name: label,
      score: Number(raw.radar.datasets[0].data[index] ?? 0),
    }));
  }

  if (!normalized.barData && Array.isArray(raw.bar?.data)) {
    normalized.barData = raw.bar.data.map((item: any) => ({
      name: item.name,
      score: Number(item.score ?? 0),
      status: item.status || 'warning',
    }));
  }

  if (!normalized.pieData && Array.isArray(raw.severity_distribution?.data)) {
    const severityMap: Record<string, 'critical' | 'warning' | 'good'> = {
      Critical: 'critical',
      Warning: 'warning',
      Minor: 'good',
    };
    normalized.pieData = raw.severity_distribution.data.flatMap((entry: any) => {
      const count = Math.max(0, Number(entry.value ?? 0));
      const severity = severityMap[entry.name] || 'warning';
      return Array.from({ length: count }).map(() => ({ severity }));
    });
  }

  return normalized;
}

function formatReviewDate(isoString?: string | null): string {
  if (!isoString) return '';
  const utcString = isoString.endsWith('Z') ? isoString : `${isoString}Z`;
  const d = new Date(utcString);
  if (Number.isNaN(d.getTime())) return '';
  return new Intl.DateTimeFormat('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  }).format(d);
}

function overallBand(score: number): 'good' | 'warning' | 'critical' {
  if (score >= 80) return 'good';
  if (score >= 60) return 'warning';
  return 'critical';
}

interface WorkspaceAppProps {
  config: WorkspaceConfig;
}

export function WorkspaceApp({ config }: WorkspaceAppProps) {
  const [evaluationId, setEvaluationId] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>('idle');
  const [progressMsg, setProgressMsg] = useState('');
  const [results, setResults] = useState<any>(null);
  const [charts, setCharts] = useState<any>(null);
  const [isKbOpen, setIsKbOpen] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);

  // Polling for async job
  useEffect(() => {
    let intervalId: NodeJS.Timeout;

    const pollJob = async () => {
      if (!jobId) return;
      try {
        const res = await fetch(`${config.apiBaseUrl}/job/${jobId}`);
        const data = await res.json();
        
        setStatus(data.status);
        setProgressMsg(data.progress_message);

        if (data.status === 'completed' && data.evaluation_id) {
          setEvaluationId(data.evaluation_id);
          setJobId(null);
          setHistoryRefreshKey((prev) => prev + 1);
        } else if (data.status === 'failed') {
          setJobId(null);
        }
      } catch (err) {
        console.error('Failed to poll job status:', err);
      }
    };

    if (jobId && (status === 'queued' || status === 'processing')) {
      intervalId = setInterval(pollJob, 2000);
    }
    return () => clearInterval(intervalId);
  }, [jobId, status, config.apiBaseUrl]);

  // Fetch results when evaluationId is set
  useEffect(() => {
    if (!evaluationId) return;
    const fetchResults = async () => {
      try {
        const res = await fetch(`${config.apiBaseUrl}/evaluation/${evaluationId}`);
        if (res.ok) {
          const data = await res.json();
          setResults(data);
          const nextId = data?.evaluation_id || data?.id;
          if (nextId && nextId !== evaluationId) {
            setEvaluationId(nextId);
          }
          setStatus('completed');
        }
      } catch (err) {
        console.error('Failed to fetch evaluation results:', err);
      }
    };
    const fetchCharts = async () => {
      try {
        const res = await fetch(`${config.apiBaseUrl}/evaluation/${evaluationId}/charts`);
        if (res.ok) {
          const raw = await res.json();
          setCharts(normalizeChartsPayload(raw));
        }
      } catch (err) {
        console.error('Failed to fetch charts:', err);
      }
    };
    fetchResults();
    fetchCharts();
  }, [evaluationId, config.apiBaseUrl]);

  const handleUploadStart = (job: any) => {
    if (job.job_id) {
      setJobId(job.job_id);
      setStatus('queued');
      setProgressMsg('Job queued...');
    } else {
      // Fallback for direct sync response
      setResults(job);
      setStatus('completed');
      setEvaluationId(job.evaluation_id || job.id || null);
      setHistoryRefreshKey((prev) => prev + 1);
    }
  };

  const handleReset = () => {
    setEvaluationId(null);
    setJobId(null);
    setResults(null);
    setCharts(null);
    setStatus('idle');
    setProgressMsg('');
  };

  const downloadReport = () => {
    const reportId = evaluationId || results?.evaluation_id || results?.id;
    if (reportId) {
      window.open(`${config.apiBaseUrl}/evaluation/${reportId}/report`, '_blank');
    }
  };

  const primaryStyle = { color: config.theme.primary };
  const bgStyle = { backgroundColor: config.theme.primary };
  const showPdfReport = config.hasPdfReport || config.workspace === 'compliance';

  const chartStroke = config.theme.chartStroke ?? config.theme.accent;

  return (
    <div className="min-h-screen bg-[#F4F7FB] flex flex-col font-sans text-gray-900">
      {/* Header */}
      <header className={`bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between sticky top-0 z-40 shadow-sm`}>
        <div className="flex items-center gap-4">
          <button 
            onClick={() => window.location.href = '/'}
            className="p-2 hover:bg-gray-100 rounded-full transition-colors text-gray-500 hover:text-gray-900 focus:outline-none focus:ring-2 focus:ring-offset-2"
            style={{ '--tw-ring-color': config.theme.primary } as any}
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-gray-900 flex items-center gap-2">
              {config.title}
            </h1>
            <p className="text-sm text-gray-500 font-medium">{config.subtitle}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsHistoryOpen(true)}
            className="px-4 py-2 text-sm font-semibold text-gray-700 bg-white border border-gray-300 rounded-lg shadow-sm hover:bg-gray-50 transition-all focus:outline-none focus:ring-2 focus:ring-offset-2"
            style={{ '--tw-ring-color': config.theme.primary } as any}
          >
            History
          </button>
          <button
            onClick={() => setIsKbOpen(true)}
            className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white rounded-lg shadow-sm hover:opacity-90 transition-all focus:outline-none focus:ring-2 focus:ring-offset-2"
            style={{ backgroundColor: config.theme.primary, '--tw-ring-color': config.theme.primary } as any}
          >
            <Database className="w-4 h-4" />
            Knowledge Base
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 md:p-8 space-y-8 animate-in fade-in duration-500">
        
        {status === 'idle' && (
          <div className="max-w-2xl mx-auto mt-12">
            <UploadCard 
              onUploadComplete={handleUploadStart} 
              apiEndpoint={`${config.apiBaseUrl}/evaluate`}
            />
          </div>
        )}

        {(status === 'queued' || status === 'processing') && (
          <div className="max-w-2xl mx-auto mt-12 text-center space-y-6">
             <div className="relative pt-1">
              <div className="flex mb-2 items-center justify-between">
                <div>
                  <span className="text-xs font-semibold inline-block py-1 px-2 uppercase rounded-full" style={{ color: config.theme.primary, backgroundColor: `${config.theme.primary}20` }}>
                    {status}
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-xs font-semibold inline-block" style={primaryStyle}>
                    Analyzing...
                  </span>
                </div>
              </div>
              <div className="overflow-hidden h-2 mb-4 text-xs flex rounded bg-blue-100">
                <div style={{ width: "60%", backgroundColor: config.theme.primary }} className="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center animate-pulse"></div>
              </div>
            </div>
            <p className="text-lg font-medium text-gray-700">{progressMsg}</p>
          </div>
        )}

        {status === 'completed' && results && (() => {
          const { coreMetrics, typeMetrics } = deriveCoreAndTypeMetrics(results);
          const integrityScore = averageScores(coreMetrics);
          const lowestMetric = coreMetrics
            .slice()
            .sort((a: any, b: any) => (Number(a.score) || 0) - (Number(b.score) || 0))[0];
          const bankingMetricsAvg = Array.isArray(results.banking_metrics) && results.banking_metrics.length
            ? averageScores(results.banking_metrics)
            : null;
          const standardsAvg =
            typeMetrics.length > 0
              ? averageScores(typeMetrics)
              : config.workspace === 'banking' && results.banking_overall_score != null
                ? Number(results.banking_overall_score)
                : config.workspace === 'banking'
                  ? (bankingMetricsAvg != null ? Number(bankingMetricsAvg) : null)
                  : null;
          const chartAccent = chartStroke;
          const issues = Array.isArray(results.issues) ? results.issues : [];
          const criticalCount = issues.filter((i: any) => i.severity === 'critical').length;
          const warningCount = issues.filter((i: any) => i.severity === 'warning').length;
          const reviewDate = formatReviewDate(results.created_at);
          const reviewId = results.evaluation_id || results.short_id || '';

          return (
          <div className="space-y-10 animate-in slide-in-from-bottom-4 duration-500 pb-12">
            <section className="bg-white rounded-2xl border border-gray-100/90 shadow-sm p-6 md:p-8">
              <div className="flex flex-col lg:flex-row gap-8 lg:gap-10 items-start">
                <div className="flex-shrink-0 mx-auto lg:mx-0 pt-1">
                  <ScoreCircle
                    score={Number(results.overall_score) || 0}
                    statusBand={overallBand(Number(results.overall_score) || 0)}
                  />
                </div>
                <div className="flex-1 w-full min-w-0 space-y-5">
                  <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                    <div className="min-w-0">
                      <h2 className="text-2xl md:text-3xl font-bold text-gray-900 tracking-tight break-words">
                        Overall Document Quality Score
                      </h2>
                      <p className="text-sm text-gray-500 mt-2">
                        This score represents the aggregated evaluation across all defined data quality dimensions.
                      </p>
                      <div className="flex flex-wrap items-center gap-2 mt-3">
                        <span className="px-3 py-1.5 bg-gray-50 text-gray-700 rounded-lg text-sm font-medium border border-gray-200/90">
                          File: {results.filename}
                        </span>
                        <span className="px-3 py-1.5 bg-gray-50 text-gray-700 rounded-lg text-sm font-medium border border-gray-200/90">
                          Type: {results.document_type || 'Unknown'}
                        </span>
                        <StatusBadge status={results.overall_status} />
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2 shrink-0">
                      {showPdfReport && (
                        <button
                          type="button"
                          onClick={downloadReport}
                          className="flex items-center gap-2 px-4 py-2.5 text-sm font-semibold text-white rounded-xl shadow-sm hover:opacity-90 transition-all"
                          style={bgStyle}
                        >
                          <Download className="w-4 h-4" />
                          Export PDF
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={handleReset}
                        className="px-4 py-2.5 text-sm font-semibold text-gray-700 bg-white border border-gray-200 rounded-xl shadow-sm hover:bg-gray-50 transition-all"
                      >
                        New Analysis
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section className="space-y-4">
              <p className="text-[11px] font-bold uppercase tracking-widest text-gray-400">
                Quality dimensions
              </p>
              <QualityDimensionsRow
                integrityScore={integrityScore}
                standardsScore={standardsAvg}
                primaryColor={config.theme.primary}
                integrityLabel="Document integrity score"
                standardsLabel={
                  config.workspace === 'banking'
                    ? 'Regulatory & domain quality'
                    : 'AI risk assessment quality'
                }
                issuesSummary={{
                  total: issues.length,
                  critical: criticalCount,
                  warning: warningCount,
                  mostAffected: lowestMetric?.name,
                }}
                reviewInfo={{
                  reviewedAt: reviewDate,
                  filename: results.filename,
                  evaluationId: reviewId,
                }}
              />
            </section>

            <ExecutiveSummary
              executiveSummary={results.executive_summary}
              riskSummary={results.risk_summary}
              recommendations={results.recommendations}
              documentType={results.document_type}
              primaryColor={config.theme.primary}
            />

            {config.hasLegalHold && results.legal_hold && (
              <AlertBox
                type="warning"
                title="LEGAL HOLD IMPOSED"
                message={results.legal_hold_reason || 'This document has triggered a legal hold rule.'}
              />
            )}

            {charts && charts.radarData?.length > 0 && (
              <section className="space-y-4">
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-widest text-gray-400 mb-1">
                    Visualization
                  </p>
                  <h3 className="text-xl font-bold text-gray-900">Visual Analytics</h3>
                </div>
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                  <div className="bg-white rounded-2xl border border-gray-100/90 shadow-sm p-6 flex flex-col min-h-[320px]">
                    <h4 className="text-sm font-bold text-gray-900 mb-1">Metric Comparison</h4>
                    <p className="text-xs text-gray-500 mb-4">Core dimensions at a glance</p>
                    <div className="flex-1 min-h-[260px]">
                      <MetricRadarChart
                        embedded
                        metrics={charts.radarData}
                        strokeColor={chartAccent}
                        fillColor={chartAccent}
                      />
                    </div>
                  </div>
                  <div className="bg-white rounded-2xl border border-gray-100/90 shadow-sm p-6 flex flex-col min-h-[320px]">
                    <h4 className="text-sm font-bold text-gray-900 mb-1">Core Metric Scores</h4>
                    <p className="text-xs text-gray-500 mb-4">Percent scores by dimension</p>
                    <div className="flex-1 min-h-[260px]">
                      <MetricBarChart embedded metrics={charts.barData} />
                    </div>
                  </div>
                </div>
              </section>
            )}

            <section className="space-y-4">
              <h3 className="text-xl font-bold text-gray-900 tracking-tight">Core Quality Metrics</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
                {coreMetrics.map((metric: any, index: number) => (
                  <MetricCard
                    key={metric.id || `core-${index}`}
                    name={metric.name}
                    score={metric.score}
                    description={metric.description}
                    statusMessage={metric.status_message}
                    status={metric.status as 'good' | 'warning' | 'critical'}
                    explanation={config.workspace === 'compliance' ? (metric.methodology || metric.description) : metric.reasoning}
                    issueDetails={metric.reasoning || metric.status_message}
                    showLinkedStandards={false}
                    accentColor={chartAccent}
                  />
                ))}
              </div>
            </section>

            {config.hasLinkedStandards && typeMetrics.length > 0 && (
              <section className="space-y-4">
                <div className="flex flex-wrap items-center gap-3">
                  <h3 className="text-xl font-bold text-gray-900 tracking-tight">Standards-Specific Metrics</h3>
                  {config.standardsSectionBadge && (
                    <span className="px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wide bg-sky-100 text-sky-900 border border-sky-200/80">
                      {config.standardsSectionBadge}
                    </span>
                  )}
                  <span className="text-sm text-gray-500">({typeMetrics.length} metrics)</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
                  {typeMetrics.map((metric: any, index: number) => (
                    <MetricCard
                      key={metric.id || `type-${index}`}
                      name={metric.name}
                      score={metric.score}
                      description={metric.description}
                      statusMessage={metric.status_message}
                      status={metric.status as 'good' | 'warning' | 'critical'}
                      explanation={config.workspace === 'compliance' ? (metric.methodology || metric.description) : metric.reasoning}
                      issueDetails={metric.reasoning || metric.status_message}
                      standardsBadge={
                        metric.linked_standards?.length
                          ? metric.linked_standards
                              .map((ls: any) => `${ls.standard_id} ${ls.clause}`.trim())
                              .join(', ')
                          : undefined
                      }
                      showLinkedStandards
                      accentColor={chartAccent}
                    />
                  ))}
                </div>
              </section>
            )}

            {config.hasDomainMetrics && Array.isArray(results.banking_metrics) && results.banking_metrics.length > 0 && (
              <div className="space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                  <h3 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                    <span className="w-1.5 h-6 rounded-full shrink-0" style={bgStyle} />
                    Domain intelligence ({results.banking_domain || 'Banking'})
                  </h3>
                  <div className="flex items-center gap-3 text-sm text-gray-500">
                    <span>Domain match confidence</span>
                    <span className="px-3 py-1 bg-blue-50 text-blue-800 rounded-lg text-xs font-bold border border-blue-100">
                      High
                    </span>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
                  {results.banking_metrics.map((m: any, idx: number) => (
                    <BankingMetricCard key={m.metric_code || m.name || idx} metric={m} />
                  ))}
                </div>
              </div>
            )}

            <section className="space-y-3">
              <IssuesTable issues={results.issues} showRegulation={config.workspace === 'banking'} />
            </section>

            {config.footerTagline && (
              <p className="text-center text-xs text-gray-400 pt-2">{config.footerTagline}</p>
            )}
          </div>
          );
        })()}
      </main>

      <HistoryModal
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        apiBaseUrl={config.apiBaseUrl}
        refreshKey={historyRefreshKey}
        onSelect={(id) => {
          setEvaluationId(id);
          setIsHistoryOpen(false);
        }}
        showDomainFilter={config.workspace === 'banking'}
      />

      <KnowledgeBasePanel 
        isOpen={isKbOpen} 
        onClose={() => setIsKbOpen(false)} 
        apiBaseUrl={`${config.apiBaseUrl}/knowledge-base`}
        workspace={config.workspace}
      />
    </div>
  );
}
