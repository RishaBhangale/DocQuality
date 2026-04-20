import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, FileText, Building2, Download, History, ChevronDown, ChevronUp, ClipboardList, ShieldAlert, CalendarDays, FolderOpen } from 'lucide-react';
import { UploadCard } from './components/UploadCard';
import { MetricCard } from './components/MetricCard';
import { IssuesTable } from './components/IssuesTable';
import { MetricExplanation } from './components/MetricExplanation';
import { StatusBadge } from './components/StatusBadge';
import { MetricRadarChart } from './components/MetricRadarChart';
import { MetricBarChart } from './components/MetricBarChart';
import { ExecutiveSummary } from './components/ExecutiveSummary';
import { AlertBox } from './components/AlertBox';
import { BankingMetricCard } from './components/BankingMetricCard';
import { BankingScoreCard } from './components/BankingScoreCard';
import { BankingRadarChart } from './components/BankingRadarChart';
import { getDomainQualityLabel } from './utils/domainLabels';
import type { BankingMetric } from './components/BankingMetricCard';

// ── Types ─────────────────────────────────────────────────────────────────────

interface Metric {
  name: string;
  score: number;
  description: string;
  status_message: string;
  status: 'good' | 'warning' | 'critical';
  weight: number;
  reasoning: string;
}

interface Issue {
  field_name: string;
  issue_type: string;
  description: string;
  severity: 'good' | 'warning' | 'critical';
  regulation_reference?: string;
  metric_dimension?: string;
}

interface RemediationItem {
  priority: string;
  action: string;
  regulation?: string;
  deadline?: string;
  responsible_party?: string;
}

interface EvaluationResult {
  evaluation_id: string;
  filename: string;
  document_type: string;
  overall_score: number;
  overall_status: 'good' | 'warning' | 'critical';
  metrics: Metric[];
  issues: Issue[];
  executive_summary: string;
  risk_summary: string;
  recommendations: string[];
  created_at: string;
  // Banking domain intelligence
  banking_domain?: string | null;
  banking_metrics?: BankingMetric[];
  banking_overall_score?: number | null;
  legal_hold?: boolean;
  legal_hold_reason?: string;
  remediation_plan?: RemediationItem[];
}

interface JobStatus {
  job_id: string;
  filename: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress_message: string;
  evaluation_id?: string;
  error_message?: string;
}

interface EvaluationListItem {
  evaluation_id: string;
  filename: string;
  document_type: string;
  banking_domain?: string;
  overall_score: number;
  banking_overall_score?: number;
  legal_hold?: boolean;
  created_at: string;
}

// ── API ────────────────────────────────────────────────────────────────────────

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/banking';

// ── Helpers ───────────────────────────────────────────────────────────────────

function mapMetricToCardProps(m: Metric) {
  return {
    name: m.name,
    score: m.score,
    description: m.description,
    statusMessage: m.status_message,
    status: m.status,
  };
}

function mapIssuesToTableProps(issues: Issue[]) {
  return issues.map((i) => ({
    fieldName: i.field_name,
    issueType: i.issue_type,
    description: i.description,
    severity: i.severity,
    regulationReference: i.regulation_reference,
    metricDimension: i.metric_dimension,
  }));
}

const PRIORITY_COLORS: Record<string, string> = {
  High: 'bg-red-50 border-red-200 text-red-800',
  Medium: 'bg-yellow-50 border-yellow-200 text-yellow-800',
  Low: 'bg-green-50 border-green-200 text-green-800',
};

// ── Component ─────────────────────────────────────────────────────────────────

export default function App() {
  const navigate = useNavigate();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [isDownloadingReport, setIsDownloadingReport] = useState(false);
  const [progressMessage, setProgressMessage] = useState<string>('');
  const [evaluationResult, setEvaluationResult] = useState<EvaluationResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // History panel
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyItems, setHistoryItems] = useState<EvaluationListItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);

  // Polling ref to cancel on unmount
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Polling ──────────────────────────────────────────────────────────────────

  const pollJob = useCallback(async (jobId: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/job/${jobId}`);
      if (!res.ok) throw new Error(`Job status error (HTTP ${res.status})`);
      const job: JobStatus = await res.json();

      setProgressMessage(job.progress_message || job.status);

      if (job.status === 'completed' && job.evaluation_id) {
        const evalRes = await fetch(`${API_BASE_URL}/api/evaluation/${job.evaluation_id}`);
        if (!evalRes.ok) throw new Error(`Fetch evaluation error (HTTP ${evalRes.status})`);
        const result: EvaluationResult = await evalRes.json();
        setEvaluationResult(result);
        setIsEvaluating(false);
        setProgressMessage('');
      } else if (job.status === 'failed') {
        setIsEvaluating(false);
        setErrorMessage(job.error_message || 'Evaluation failed.');
        setProgressMessage('');
      } else {
        pollTimeoutRef.current = setTimeout(() => pollJob(jobId), 1000);
      }
    } catch (err) {
      setIsEvaluating(false);
      setErrorMessage(err instanceof Error ? err.message : 'Polling error.');
      setProgressMessage('');
    }
  }, []);

  // Cancel polling on unmount
  useEffect(() => () => { if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current); }, []);

  // ── Handlers ─────────────────────────────────────────────────────────────────

  const handleFileSelect = (file: File) => {
    setSelectedFile(file);
    setErrorMessage(null);
  };

  const handleEvaluate = async () => {
    if (!selectedFile) return;

    setIsEvaluating(true);
    setErrorMessage(null);
    setProgressMessage('Uploading document…');

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const res = await fetch(`${API_BASE_URL}/api/evaluate`, { method: 'POST', body: formData });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(err.detail || `Upload failed (HTTP ${res.status})`);
      }

      const job = await res.json(); // {job_id, status, filename, message}
      setProgressMessage('Job queued — starting evaluation…');
      pollJob(job.job_id);
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Evaluation failed. Please try again.';
      setErrorMessage(msg);
      setIsEvaluating(false);
      setProgressMessage('');
    }
  };

  const handleNewUpload = () => {
    if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
    setSelectedFile(null);
    setEvaluationResult(null);
    setIsEvaluating(false);
    setErrorMessage(null);
    setProgressMessage('');
  };

  const handleDownloadReport = async () => {
    if (!evaluationResult) return;

    setIsDownloadingReport(true);
    setErrorMessage(null);

    try {
      const res = await fetch(`${API_BASE_URL}/api/evaluation/${evaluationResult.evaluation_id}/report`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unable to generate report.' }));
        throw new Error(err.detail || `Report download failed (HTTP ${res.status})`);
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      const baseName = evaluationResult.filename.replace(/\.[^.]+$/, '') || 'document-quality-report';
      link.href = url;
      link.download = `${baseName}-quality-report.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Unable to download report.';
      setErrorMessage(msg);
    } finally {
      setIsDownloadingReport(false);
    }
  };

  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/evaluations?limit=20`);
      if (res.ok) {
        const data = await res.json();
        setHistoryItems(data.items ?? data);
      }
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleHistoryToggle = () => {
    const next = !historyOpen;
    setHistoryOpen(next);
    if (next && historyItems.length === 0) loadHistory();
  };

  const handleLoadHistory = async (id: string) => {
    setSelectedHistoryId(id);
    const res = await fetch(`${API_BASE_URL}/api/evaluation/${id}`);
    if (res.ok) {
      const result: EvaluationResult = await res.json();
      setEvaluationResult(result);
      setHistoryOpen(false);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const getOverallStatusLabel = (status: 'good' | 'warning' | 'critical') =>
    ({ good: 'Good Quality', warning: 'Moderate Quality', critical: 'Critical Quality' }[status]);

  const getStatusFromScore = (score: number): 'good' | 'warning' | 'critical' =>
    (score >= 90 ? 'good' : score >= 70 ? 'warning' : 'critical');

  const formatDate = (value: string) => new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(new Date(value));

  const formatDateTime = (value?: string | null) => {
    if (!value) return '—';
    return new Intl.DateTimeFormat('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value));
  };

  const getStatusTone = (status: 'good' | 'warning' | 'critical') => ({
    good: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    warning: 'bg-amber-50 text-amber-700 border-amber-200',
    critical: 'bg-red-50 text-red-700 border-red-200',
  }[status]);

  const issueCounts = evaluationResult?.issues.reduce(
    (acc, issue) => {
      acc.total += 1;
      if (issue.severity === 'critical') acc.critical += 1;
      if (issue.severity === 'warning') acc.warning += 1;
      return acc;
    },
    { total: 0, critical: 0, warning: 0 }
  ) ?? { total: 0, critical: 0, warning: 0 };

  const topIssueDimensions = (() => {
    const allowed = new Set(['completeness', 'accuracy', 'consistency', 'validity', 'timeliness', 'uniqueness']);
    const counts = new Map<string, number>();
    (evaluationResult?.issues ?? []).forEach((i) => {
      const dim = (i.metric_dimension || '').toLowerCase().trim();
      if (!dim || !allowed.has(dim)) return;
      counts.set(dim, (counts.get(dim) ?? 0) + 1);
    });
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 2)
      .map(([dim, count]) => ({
        label: dim.charAt(0).toUpperCase() + dim.slice(1),
        count,
      }));
  })();

  const documentIntegrityScore = Math.round(evaluationResult?.overall_score ?? 0);
    const hasBankingDomain = !!(
      evaluationResult?.banking_domain && 
      !['none', 'null', 'unknown'].includes(evaluationResult.banking_domain.toLowerCase()) &&
      evaluationResult?.banking_overall_score != null
    );
    const domainSpecificScore = hasBankingDomain ? Math.round(evaluationResult.banking_overall_score!) : 0;
    const overallScore = hasBankingDomain
      ? Math.round((documentIntegrityScore + domainSpecificScore) / 2)
      : documentIntegrityScore;

    const compositeStatus = getStatusFromScore(overallScore);
    const documentIntegrityStatus = (evaluationResult?.overall_status as 'good' | 'warning' | 'critical')
      ?? getStatusFromScore(documentIntegrityScore);
    const domainSpecificStatus = hasBankingDomain ? getStatusFromScore(domainSpecificScore) : 'good';
  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-[#F4F7FB]">
      {/* ── Header ── */}
      <header className="relative bg-white border-b border-slate-200">
        <div className="mx-auto flex max-w-[1320px] items-center justify-between px-6 py-6 sm:px-10 xl:px-12">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-[#1E3A8A] flex items-center justify-center">
              <FileText className="w-6 h-6 text-white" />
            </div>
            <div>
              <span className="text-xl font-semibold text-gray-900">DocQuality</span>
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Review Console</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/')}
              className="hidden sm:flex px-4 py-2 border border-[#1E3A8A] text-[#1E3A8A] bg-white rounded-lg font-medium hover:bg-blue-50 transition-colors whitespace-nowrap text-sm print:hidden items-center mr-2"
            >
              Switch Workspace
            </button>
            {evaluationResult && (
              <button
                onClick={handleDownloadReport}
                disabled={isDownloadingReport}
                className="flex items-center gap-2 rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-600 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isDownloadingReport ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                Download Report
              </button>
            )}
            <button
              onClick={handleHistoryToggle}
              className="flex items-center gap-2 rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-600 transition-colors hover:bg-slate-50"
            >
              <History className="w-4 h-4" />
              History
              {historyOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
            <span className="hidden text-sm text-slate-500 sm:block">Unstructured Data Quality</span>
          </div>
        </div>

        {/* History Panel */}
        {historyOpen && (
          <div className="absolute left-0 right-0 top-full z-50">
            <div className="mx-auto max-w-[1320px] px-6 py-4 sm:px-10 xl:px-12 animate-in slide-in-from-top-1 duration-200">
              <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
              <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
                <h3 className="text-sm font-semibold text-gray-700">Recent Evaluations</h3>
                <button onClick={loadHistory} className="text-xs text-[#1E3A8A] hover:underline">Refresh</button>
              </div>

              {historyLoading ? (
                <div className="flex items-center gap-2 px-4 py-4 text-sm text-gray-400">
                  <Loader2 className="w-4 h-4 animate-spin" /> Loading…
                </div>
              ) : historyItems.length === 0 ? (
                <p className="px-4 py-4 text-sm text-gray-400">No previous evaluations found.</p>
              ) : (
                <div className="max-h-[60vh] overflow-y-auto">
                  {historyItems.map((item) => {
                    const isSelected = (evaluationResult?.evaluation_id ?? selectedHistoryId) === item.evaluation_id;

                    const integrity = item.overall_score ?? 0;
                    const hasHistBanking = !!(
                      item.banking_domain && 
                      !['none', 'null', 'unknown'].includes(item.banking_domain.toLowerCase()) &&
                      item.banking_overall_score != null
                    );
                    const compositeOverallRounded = hasHistBanking 
                      ? Math.round((integrity + item.banking_overall_score!) / 2) 
                      : Math.round(integrity);

                    const scoreTone = compositeOverallRounded >= 90
                      ? 'text-emerald-700'
                      : compositeOverallRounded >= 70
                        ? 'text-amber-700'
                        : 'text-red-700';

                    return (
                      <button
                        key={item.evaluation_id}
                        onClick={() => handleLoadHistory(item.evaluation_id)}
                        className={`w-full text-left px-4 py-3 border-b border-gray-100 last:border-0 transition-colors ${
                          isSelected ? 'bg-slate-50' : 'bg-white hover:bg-slate-50/60'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-6">
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-gray-900 truncate">{item.filename}</p>
                            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                              <span className="text-xs text-gray-500">{item.document_type}</span>
                              {hasHistBanking && item.banking_domain && (
                                <span className="text-xs text-[#1E3A8A] font-medium">{item.banking_domain}</span>
                              )}
                              {item.legal_hold && (
                                <span className="text-[11px] font-semibold text-red-600 bg-red-50 px-1.5 py-0.5 rounded">HOLD</span>
                              )}
                            </div>
                            <p className="mt-1 text-xs text-gray-400">{formatDateTime(item.created_at)}</p>
                          </div>

                          <div className="flex flex-col items-end flex-shrink-0">
                            <p className={`text-sm font-bold ${scoreTone}`}>Overall {compositeOverallRounded}%</p>
                            {isSelected && (
                              <p className="mt-1 text-[11px] font-semibold text-slate-500">Selected</p>
                            )}
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
            </div>
          </div>
        )}
      </header>

      {/* ── Main Content ── */}
      <main className="mx-auto max-w-[1320px] px-6 py-10 sm:px-10 xl:px-12">
        {!evaluationResult ? (
          /* ── Upload State ── */
          <div className="flex flex-col items-center justify-center min-h-[calc(100vh-200px)]">
            <div className="text-center mb-12 px-4">
              <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-gray-900 mb-4">
                Document Quality Intelligence
              </h1>
              <p className="text-base sm:text-lg text-gray-600 max-w-2xl mx-auto">
                Upload a document to receive a structured quality analysis across completeness,
                accuracy, consistency, validity, timeliness, and uniqueness.
                {" "}When applicable, it also includes banking-domain validation.
              </p>
            </div>

            <UploadCard onFileSelect={handleFileSelect} selectedFile={selectedFile} />

            {errorMessage && (
              <div className="mt-6 w-full max-w-[600px]">
                <AlertBox type="error" title="Evaluation Error">{errorMessage}</AlertBox>
              </div>
            )}

            {isEvaluating ? (
              <div className="mt-8 flex flex-col items-center">
                <Loader2 className="w-10 h-10 text-[#1E3A8A] animate-spin mb-4" />
                <p className="text-lg font-medium text-gray-900">Analyzing document quality…</p>
                {progressMessage && (
                  <p className="text-sm text-[#1E3A8A] mt-1 font-medium">{progressMessage}</p>
                )}
                <p className="text-xs text-gray-400 mt-1">Results will appear automatically</p>
              </div>
            ) : (
              <button
                onClick={handleEvaluate}
                disabled={!selectedFile}
                className="mt-8 px-8 py-3 bg-[#1E3A8A] text-white rounded-lg font-medium hover:bg-[#1E3A8A]/90 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                Evaluate Document
              </button>
            )}
          </div>
        ) : (
          /* ── Dashboard State ── */
          <div className="space-y-12 animate-in fade-in duration-500">
            {errorMessage && (
              <AlertBox type="error" title="Action Failed">{errorMessage}</AlertBox>
            )}

            {/* Legal Hold Banner */}
            {evaluationResult.legal_hold && (
              <div className="flex items-start gap-3 rounded-2xl bg-red-600 px-5 py-4 text-white shadow-md">
                <Building2 className="w-5 h-5 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold uppercase tracking-wide">Legal Hold Triggered</p>
                  {evaluationResult.legal_hold_reason && (
                    <p className="text-sm text-red-100 mt-0.5">{evaluationResult.legal_hold_reason}</p>
                  )}
                </div>
              </div>
            )}

            {/* Executive Summary Shell */}
            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">

              {/* Header with title and upload button */}
              <div className="mb-8 flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
                <div>
                  <h2 className="text-2xl font-bold leading-tight tracking-tight text-slate-900 sm:text-[1.65rem]">
                    Document Quality Overview
                  </h2>
                  <p className="mt-1.5 text-sm text-slate-500">
                    Two-dimensional quality evaluation for comprehensive document validation
                  </p>
                </div>
                <button
                  onClick={handleNewUpload}
                  className="shrink-0 whitespace-nowrap rounded-xl border border-[#1E3A8A] px-5 py-2.5 text-sm font-medium text-[#1E3A8A] transition-colors hover:bg-[#1E3A8A]/5"
                >
                  Upload New Document
                </button>
              </div>

              {/* ── Overall Quality Score (Hero Section) ──────────────────────── */}
              <div className="mb-12 overflow-hidden rounded-3xl border border-slate-200 bg-white p-8 shadow-lg">
                <div className="flex flex-col gap-8 sm:flex-row sm:items-center sm:justify-between">
                  {/* Left: Circle + Score */}
                  <div className="flex flex-col items-center gap-6 sm:flex-row sm:gap-8 sm:items-center">
                    <div className="flex shrink-0 flex-col items-center gap-3">
                      <div className="relative h-36 w-36">
                        <svg className="relative h-36 w-36 -rotate-90" viewBox="0 0 100 100" aria-hidden="true">
                          <circle cx="50" cy="50" r="42" fill="none" stroke="#E5E7EB" strokeWidth="12" />
                          <circle
                            cx="50"
                            cy="50"
                            r="42"
                            fill="none"
                            stroke={compositeStatus === 'good' ? '#10B981' : compositeStatus === 'warning' ? '#F59E0B' : '#EF4444'}
                            strokeWidth="12"
                            strokeLinecap="round"
                            strokeDasharray={2 * Math.PI * 42}
                            strokeDashoffset={(2 * Math.PI * 42) * (1 - overallScore / 100)}
                            className="transition-all duration-1000"
                          />
                        </svg>
                        <span className="absolute inset-0 flex flex-col items-center justify-center">
                          <span className="text-5xl font-black text-slate-900">{overallScore}</span>
                          <span className="text-xs font-semibold text-slate-400 mt-1">/100</span>
                        </span>
                      </div>

                      <span className={`inline-flex items-center rounded-lg border px-3.5 py-2 text-sm font-semibold ${getStatusTone(compositeStatus)}`}>
                        {getOverallStatusLabel(compositeStatus)}
                      </span>
                    </div>

                    <div className="flex flex-col gap-2 text-center sm:text-left">
                      <p className="text-[11px] font-bold uppercase tracking-[0.3em] text-slate-500">Overall Quality Score</p>
                      <p className="text-sm text-slate-600 leading-relaxed">
                        {hasBankingDomain 
                          ? "Composite evaluation from Document Integrity + Domain-Specific Quality" 
                          : "Derived from core Document Integrity Evaluation"}
                      </p>

                      {/* Document Type (moved under Overall Quality Score) */}
                      <div className="mt-3">
                        <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-slate-500 mb-2">Document Type</p>
                        <div className="inline-flex items-center gap-2 rounded-lg bg-blue-50 border border-blue-200 px-3.5 py-2">
                          <FileText className="h-4 w-4 text-blue-600" />
                          <span className="text-sm font-semibold text-blue-900">{evaluationResult.document_type || 'Unknown'}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                </div>
              </div>

              {/* ── Component Quality Scores (Two Dimensions) ──────────────────────── */}
              <div className="mb-6 text-sm text-slate-500">
                <p className="text-[11px] font-bold uppercase tracking-[0.25em] text-slate-400 mb-6">Quality Dimensions</p>
              </div>
              <div className={`grid grid-cols-1 gap-6 ${hasBankingDomain ? 'md:grid-cols-2' : ''}`}>
                {/* Document Integrity Score */}
                <div className="relative rounded-2xl border border-slate-200/60 bg-white p-7 shadow-sm">
                  <div className="relative flex flex-col">
                    <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-slate-500">Document Integrity Score</p>
                    <p className="mt-2 text-xs text-slate-500">Weighted baseline across completeness, accuracy, consistency, validity, timeliness & uniqueness</p>
                    
                    <div className="mt-6 flex items-center gap-6">
                      <div className="flex flex-col items-center">
                        <div className="relative h-24 w-24">
                          <svg className="relative h-24 w-24 -rotate-90" viewBox="0 0 100 100" aria-hidden="true">
                            <circle cx="50" cy="50" r="42" fill="none" stroke="#E5E7EB" strokeWidth="10" />
                            <circle
                              cx="50"
                              cy="50"
                              r="42"
                              fill="none"
                              stroke={documentIntegrityStatus === 'good' ? '#10B981' : documentIntegrityStatus === 'warning' ? '#F59E0B' : '#EF4444'}
                              strokeWidth="10"
                              strokeLinecap="round"
                              strokeDasharray={2 * Math.PI * 42}
                              strokeDashoffset={(2 * Math.PI * 42) * (1 - documentIntegrityScore / 100)}
                              className="transition-all duration-700"
                            />
                          </svg>
                          <span className="absolute inset-0 flex flex-col items-center justify-center">
                            <span className="text-2xl font-black text-slate-900">{documentIntegrityScore}</span>
                            <span className="text-[10px] font-semibold text-slate-400">/100</span>
                          </span>
                        </div>
                      </div>

                      <div className="flex-1 flex flex-col items-center justify-center text-center">
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Quality Status</p>
                        <div className="mt-2">
                          <span className={`inline-flex items-center rounded-lg border px-3.5 py-2 text-sm font-semibold ${getStatusTone(documentIntegrityStatus)}`}>
                            {getOverallStatusLabel(documentIntegrityStatus)}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Domain-Specific Quality Score */}
                {hasBankingDomain && (
                  <div className="relative rounded-2xl border border-slate-200/60 bg-white p-7 shadow-sm">
                    <div className="relative flex flex-col">
                      <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-slate-500">
                        {getDomainQualityLabel(evaluationResult.banking_domain).label}
                      </p>
                      <p className="mt-1.5 text-xs text-slate-500">
                        {getDomainQualityLabel(evaluationResult.banking_domain).subtitle}
                      </p>
                      
                      <div className="mt-7 flex items-center gap-6">
                        <div className="flex flex-col items-center">
                          <div className="relative h-24 w-24">
                            <svg className="relative h-24 w-24 -rotate-90" viewBox="0 0 100 100" aria-hidden="true">
                              <circle cx="50" cy="50" r="42" fill="none" stroke="#E5E7EB" strokeWidth="10" />
                              <circle
                                cx="50"
                                cy="50"
                                r="42"
                                fill="none"
                                stroke={domainSpecificStatus === 'good' ? '#10B981' : domainSpecificStatus === 'warning' ? '#F59E0B' : '#EF4444'}
                                strokeWidth="10"
                                strokeLinecap="round"
                                strokeDasharray={2 * Math.PI * 42}
                                strokeDashoffset={(2 * Math.PI * 42) * (1 - domainSpecificScore / 100)}
                                className="transition-all duration-700"
                              />
                            </svg>
                            <span className="absolute inset-0 flex flex-col items-center justify-center">
                              <span className="text-2xl font-black text-slate-900">{domainSpecificScore}</span>
                              <span className="text-[10px] font-semibold text-slate-400">/100</span>
                            </span>
                          </div>
                        </div>

                        <div className="flex-1 flex flex-col items-center justify-center text-center">
                          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Quality Status</p>
                          <div className="mt-2">
                            <span className={`inline-flex items-center rounded-lg border px-3.5 py-2 text-sm font-semibold ${getStatusTone(domainSpecificStatus)}`}>
                              {getOverallStatusLabel(domainSpecificStatus)}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* ── Supporting Metrics Row ─────────────────────────────────────── */}
              <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-2">
                {/* Issues Flagged */}
                <div className="rounded-2xl border border-slate-200 bg-white p-7">
                  <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-slate-500">Issues Flagged</p>
                  <div className="mt-4 flex items-start justify-between gap-8">
                    <div className="flex items-end gap-3">
                      <p className="text-5xl font-black leading-none text-slate-900">{issueCounts.total}</p>
                      <p className="pb-1 text-3xl font-semibold text-slate-400">total</p>
                    </div>

                    <div className="flex flex-col gap-3 text-sm">
                      <span className="inline-flex items-center gap-2 text-red-600">
                        <span className="h-2.5 w-2.5 rounded-full bg-red-500" />
                        <span className="text-base font-bold">{issueCounts.critical} Critical</span>
                      </span>
                      <span className="inline-flex items-center gap-2 text-amber-600">
                        <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
                        <span className="text-base font-bold">{issueCounts.warning} Moderate</span>
                      </span>
                    </div>
                  </div>

                  {topIssueDimensions.length > 0 && (
                    <p className="mt-4 text-xs text-slate-500">
                      <span className="font-semibold text-slate-600">Most affected:</span>{' '}
                      {topIssueDimensions.map((d, idx) => (
                        <span key={d.label}>
                          {d.label} ({d.count}){idx < topIssueDimensions.length - 1 ? ' · ' : ''}
                        </span>
                      ))}
                    </p>
                  )}
                </div>

                {/* Review Metadata */}
                <div className="relative rounded-2xl border border-slate-200/60 bg-white p-7 shadow-sm">
                  <div className="relative">
                    <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-slate-500 mb-5">Review Information</p>
                    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                      <div>
                        <p className="text-xs text-slate-500 font-semibold uppercase tracking-wide mb-2">Review Date</p>
                        <p className="text-2xl font-bold text-slate-900">{formatDate(evaluationResult.created_at)}</p>
                      </div>

                      <div>
                        <p className="text-xs text-slate-500 font-semibold uppercase tracking-wide mb-2">ID</p>
                        <p className="text-sm font-mono font-semibold text-slate-900 break-all">{evaluationResult.evaluation_id}</p>
                      </div>

                      <div className="sm:col-span-2">
                        <p className="text-xs text-slate-500 font-semibold uppercase tracking-wide mb-2">File</p>
                        <p className="text-sm font-semibold text-slate-900 break-words">{evaluationResult.filename}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

            </section>

            {/* Executive Summary */}
            <ExecutiveSummary
              executiveSummary={evaluationResult.executive_summary}
              riskSummary={evaluationResult.risk_summary}
              recommendations={evaluationResult.recommendations}
              documentType={evaluationResult.document_type}
            />

            {/* Visual Analytics */}
            <div>
              <h2 className="text-2xl sm:text-3xl font-bold text-gray-900 mb-6">Visual Analytics</h2>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <MetricRadarChart
                  metrics={evaluationResult.metrics.map((m) => ({ name: m.name, score: m.score }))}
                />
                <MetricBarChart
                  metrics={evaluationResult.metrics.map((m) => ({ name: m.name, score: m.score, status: m.status }))}
                />
              </div>
            </div>

            {/* Quality Breakdown */}
            <div>
              <h2 className="text-2xl sm:text-3xl font-bold text-gray-900 mb-6">Quality Breakdown</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {evaluationResult.metrics.map((metric, index) => (
                  <div key={metric.name} className="animate-in fade-in" style={{ animationDelay: `${index * 100}ms`, animationFillMode: 'backwards' }}>
                    <MetricCard {...mapMetricToCardProps(metric)} />
                  </div>
                ))}
              </div>
            </div>

            {/* Banking Domain Metrics */}
            {hasBankingDomain && evaluationResult.banking_metrics && evaluationResult.banking_metrics.length > 0 && (
              <div className="animate-in fade-in">
                <div className="mb-6">
                  <h2 className="text-2xl sm:text-3xl font-bold text-gray-900">Banking Domain Metrics</h2>
                  <p className="text-sm text-[#1E3A8A] font-medium mt-0.5">{evaluationResult.banking_domain}</p>
                </div>

                <div className="mb-6 px-5 py-4 rounded-lg bg-[#1E3A8A]/5 border border-[#1E3A8A]/20">
                  <p className="text-sm text-[#1E3A8A] leading-relaxed">
                    <span className="font-semibold">Domain-specific evaluation active.</span>{' '}
                    The following metrics apply the 70/30 deterministic/AI blending model tailored to regulatory
                    requirements for <span className="font-semibold">{evaluationResult.banking_domain}</span>{' '}
                    documents. Hover <span className="font-semibold">ⓘ</span> on any card for formula, logic, and risk impact.
                  </p>
                </div>

                {/* Banking Radar Chart */}
                <div className="mb-6">
                  <BankingRadarChart
                    metrics={evaluationResult.banking_metrics}
                    bankingOverallScore={evaluationResult.banking_overall_score ?? undefined}
                    bankingDomain={evaluationResult.banking_domain}
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {evaluationResult.banking_metrics.map((metric, index) => (
                    <div key={metric.name} className="animate-in fade-in" style={{ animationDelay: `${index * 120}ms`, animationFillMode: 'backwards' }}>
                      <BankingMetricCard metric={metric} />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Remediation Plan */}
            {evaluationResult.remediation_plan && evaluationResult.remediation_plan.length > 0 && (
              <div className="bg-white rounded-lg p-6 sm:p-8 shadow-sm border border-gray-100 animate-in fade-in">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-9 h-9 rounded-lg bg-amber-600 flex items-center justify-center flex-shrink-0">
                    <ClipboardList className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h2 className="text-2xl sm:text-3xl font-bold text-gray-900">Remediation Plan</h2>
                    <p className="text-sm text-amber-600 font-medium mt-0.5">
                      {evaluationResult.remediation_plan.length} prioritised action{evaluationResult.remediation_plan.length > 1 ? 's' : ''}
                    </p>
                  </div>
                </div>

                <ol className="space-y-3">
                  {evaluationResult.remediation_plan.map((item, i) => (
                    <li
                      key={i}
                      className={`flex gap-4 p-4 rounded-lg border ${PRIORITY_COLORS[item.priority] ?? PRIORITY_COLORS.Medium}`}
                    >
                      <span className="flex-shrink-0 w-6 h-6 rounded-full bg-white/60 flex items-center justify-center text-xs font-bold">{i + 1}</span>
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2 mb-1">
                          <span className="text-xs font-bold uppercase tracking-wide opacity-60">{item.priority} Priority</span>
                          {item.regulation && (
                            <span className="text-xs px-2 py-0.5 rounded-full bg-white/60 font-medium">{item.regulation}</span>
                          )}
                        </div>
                        <p className="text-sm font-medium">{item.action}</p>
                        <div className="flex flex-wrap gap-3 mt-1.5 text-xs opacity-70">
                          {item.deadline && <span>⏱ {item.deadline}</span>}
                          {item.responsible_party && <span>👤 {item.responsible_party}</span>}
                        </div>
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {/* Issues */}
            <div className="space-y-6">
              <IssuesTable issues={mapIssuesToTableProps(evaluationResult.issues)} />
            </div>

            {/* Metric Explanation */}
            <MetricExplanation
              bankingDomain={hasBankingDomain ? evaluationResult.banking_domain : undefined}
              bankingMetrics={hasBankingDomain ? evaluationResult.banking_metrics : undefined}
            />
          </div>
        )}
      </main>

      {/* ── Footer ── */}
      <footer className="mt-24 border-t border-gray-200">
        <div className="mx-auto flex max-w-[1320px] flex-col items-center justify-between gap-4 px-6 py-8 sm:flex-row sm:px-10 xl:px-12">
          <span className="text-sm text-gray-500">Document Quality Engine v2.0</span>
          <span className="text-sm text-gray-500">Powered by AI-assisted evaluation</span>
        </div>
      </footer>
    </div>
  );
}