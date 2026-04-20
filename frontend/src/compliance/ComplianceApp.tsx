import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertCircle,
  CheckCircle2,
  FileText,
  Upload,
  X,
  ChevronDown,
  LayoutDashboard,
  ShieldCheck,
  FileSearch,
  Loader2,
  Circle,
  FileWarning,
  Activity,
  Wrench,
  Printer,
  Download,
  HelpCircle,
  Copy,
  Check,
  Clock
} from 'lucide-react';
import { UploadCard } from './components/UploadCard';
import { ScoreCircle } from './components/ScoreCircle';
import { MetricCard } from './components/MetricCard';
import { IssuesTable } from './components/IssuesTable';
import { StatusBadge } from './components/StatusBadge';
import { MetricRadarChart } from './components/MetricRadarChart';
import { MetricBarChart } from './components/MetricBarChart';
import { HistoryModal } from './components/HistoryModal';

import { ExecutiveSummary } from './components/ExecutiveSummary';
import { AlertBox } from './components/AlertBox';
import { KnowledgeBasePanel } from '../shared/KnowledgeBasePanel';

// --- Types matching backend API response ---

interface LinkedStandard {
  standard_id: string;
  control_id: string;
  clause: string;
  description: string;
}

interface Metric {
  id: string;
  name: string;
  category: 'core' | 'type_specific';
  score: number;
  description: string;
  status_message: string;
  status: 'good' | 'warning' | 'critical';
  weight: number;
  reasoning: string;
  linked_standards: LinkedStandard[];
}

interface Issue {
  field_name: string;
  issue_type: string;
  description: string;
  severity: 'good' | 'warning' | 'critical';
  metric_name?: string;
}

interface EvaluationResult {
  evaluation_id: string;
  filename: string;
  document_type: string;
  semantic_type: string;
  overall_score: number;
  overall_status: 'good' | 'warning' | 'critical';
  core_metrics: Metric[];
  type_specific_metrics: Metric[];
  primary_type_metrics: Metric[];
  metrics: Metric[];
  issues: Issue[];
  executive_summary: string;
  risk_summary: string;
  recommendations: string[];
  pipeline_status?: Record<string, string | number>;
  corrections_count?: number;
  short_id?: string;
  created_at: string;
}

interface CorrectionProposal {
  id: number;
  metric_id: string;
  field_path: string;
  current_value: string | null;
  proposed_value: string;
  reason: string;
  auto_applicable: boolean;
  applied: boolean;
}

// --- API Configuration ---

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/compliance';

/**
 * Calls the real backend API to evaluate a document.
 * Sends the file as multipart/form-data to POST /api/evaluate.
 */
const evaluateDocument = async (file: File): Promise<EvaluationResult> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/api/evaluate`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(errorData.detail || `Evaluation failed (HTTP ${response.status})`);
  }

  return response.json();
};

// --- Helper: map backend response to frontend props ---

function mapMetricToCardProps(m: Metric) {
  const standardsBadge = m.linked_standards && m.linked_standards.length > 0
    ? m.linked_standards.map(ls => `${ls.standard_id.replace('_', ' ')} ${ls.clause}`).join(', ')
    : '';
  return {
    name: m.name,
    score: m.score,
    description: m.description,
    statusMessage: m.status_message,
    status: m.status,
    explanation: m.description,
    issueDetails: m.reasoning,
    standardsBadge,
  };
}

function mapIssuesToTableProps(issues: Issue[]) {
  return issues.map(issue => ({
    fieldName: issue.field_name,
    issueType: issue.issue_type,
    description: issue.description,
    severity: issue.severity,
    metricName: issue.metric_name,
  }));
}

// --- Evaluation Progress Steps Component ---
const EVALUATION_STEPS = [
  { label: 'Extracting text from document', duration: 2000 },
  { label: 'Classifying document type', duration: 3000 },
  { label: 'Running quality & compliance analysis', duration: 8000 },
  { label: 'Computing metric scores', duration: 3000 },
  { label: 'Building evaluation report', duration: 2000 },
];

function EvaluationProgress() {
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    if (currentStep >= EVALUATION_STEPS.length) return;

    const timer = setTimeout(() => {
      setCurrentStep((prev) => Math.min(prev + 1, EVALUATION_STEPS.length));
    }, EVALUATION_STEPS[currentStep].duration);

    return () => clearTimeout(timer);
  }, [currentStep]);

  return (
    <div className="space-y-3">
      {EVALUATION_STEPS.map((step, index) => {
        const isComplete = index < currentStep;
        const isActive = index === currentStep;

        return (
          <div key={index} className="flex items-center gap-3">
            {isComplete ? (
              <CheckCircle2 className="w-5 h-5 text-[#16A34A] flex-shrink-0" />
            ) : isActive ? (
              <Loader2 className="w-5 h-5 text-[#1E3A8A] animate-spin flex-shrink-0" />
            ) : (
              <Circle className="w-5 h-5 text-gray-300 flex-shrink-0" />
            )}
            <span
              className={`text-sm transition-colors ${isComplete
                  ? 'text-[#16A34A] font-medium'
                  : isActive
                    ? 'text-gray-900 font-medium'
                    : 'text-gray-400'
                }`}
            >
              {step.label}
            </span>
          </div>
        );
      })}
      <div className="mt-4 w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
        <div
          className="bg-[#1E3A8A] h-1.5 rounded-full transition-all duration-1000 ease-out"
          style={{ width: `${(currentStep / EVALUATION_STEPS.length) * 100}%` }}
        />
      </div>
    </div>
  );
}

// --- Score Color Helper (#7: Granular Color-Coded Badges) ---
function getScoreColor(score: number): { bg: string; text: string } {
  if (score >= 80) return { bg: 'bg-[#16A34A]/10', text: 'text-[#16A34A]' };
  if (score >= 50) return { bg: 'bg-[#EAB308]/10', text: 'text-[#CA8A04]' };
  if (score >= 30) return { bg: 'bg-[#F97316]/10', text: 'text-[#EA580C]' };
  return { bg: 'bg-[#DC2626]/10', text: 'text-[#DC2626]' };
}

export default function App() {
  const navigate = useNavigate();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [evaluationResult, setEvaluationResult] = useState<EvaluationResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isHistoryView, setIsHistoryView] = useState(false);

  useEffect(() => {
    const searchParams = new URLSearchParams(window.location.search);
    const historyId = searchParams.get('id');

    if (historyId) {
      setIsEvaluating(true);
      setIsHistoryView(true);
      fetch(`${API_BASE_URL}/api/evaluation/${historyId}`)
        .then(res => {
          if (!res.ok) throw new Error("Failed to load history");
          return res.json();
        })
        .then(data => setEvaluationResult(data))
        .catch(err => setErrorMessage(err.message))
        .finally(() => setIsEvaluating(false));
    }
  }, []);

  // Phase 2: Corrections fetching
  const [correctionsData, setCorrectionsData] = useState<{ grouped: Record<string, CorrectionProposal[]>, total: number } | null>(null);
  const [isLoadingCorrections, setIsLoadingCorrections] = useState(false);

  useEffect(() => {
    if (evaluationResult?.evaluation_id) {
      setIsLoadingCorrections(true);
      fetch(`${API_BASE_URL}/api/evaluations/${evaluationResult.evaluation_id}/corrections`)
        .then(res => res.ok ? res.json() : null)
        .then(data => {
          if (data) setCorrectionsData(data);
        })
        .catch(err => console.error("Failed to fetch corrections:", err))
        .finally(() => setIsLoadingCorrections(false));
    } else {
      setCorrectionsData(null);
    }
  }, [evaluationResult?.evaluation_id]);

  const [applyingFixId, setApplyingFixId] = useState<number | null>(null);

  const handleApplyFix = async (proposalId: number) => {
    if (!evaluationResult?.evaluation_id) return;
    setApplyingFixId(proposalId);
    
    try {
      const resp = await fetch(`${API_BASE_URL}/api/evaluations/${evaluationResult.evaluation_id}/corrections/${proposalId}/apply`, {
        method: 'POST',
      });
      
      if (resp.ok) {
        setCorrectionsData(prev => {
          if (!prev) return prev;
          const newGrouped = { ...prev.grouped };
          for (const key of Object.keys(newGrouped)) {
            newGrouped[key] = newGrouped[key].map(p => 
              p.id === proposalId ? { ...p, applied: true } : p
            );
          }
          return { ...prev, grouped: newGrouped };
        });
      } else {
        console.error("Failed to apply fix", await resp.text());
      }
    } catch (e) {
      console.error("Error applying fix:", e);
    } finally {
      setApplyingFixId(null);
    }
  };

  const hasAppliedFixes = Object.values(correctionsData?.grouped || {}).flat().some(p => p.applied);

  const handleFileSelect = (file: File) => {
    setSelectedFile(file);
    setErrorMessage(null);
  };

  const handleEvaluate = async () => {
    if (!selectedFile) return;

    setIsEvaluating(true);
    setErrorMessage(null);

    try {
      const result = await evaluateDocument(selectedFile);
      setEvaluationResult(result);
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Evaluation failed. Please try again.';
      setErrorMessage(msg);
      console.error('Evaluation failed:', error);
    } finally {
      setIsEvaluating(false);
    }
  };

  const handleDownloadReport = () => {
    window.print();
  };

  const dashboardRef = useRef<HTMLDivElement>(null);

  const handleNewUpload = () => {
    setSelectedFile(null);
    setEvaluationResult(null);
    setIsEvaluating(false);
    setErrorMessage(null);
  };

  const getOverallStatusLabel = (status: 'good' | 'warning' | 'critical') => {
    const labels = {
      good: 'Good Quality',
      warning: 'Moderate Quality',
      critical: 'Critical Issues Detected',
    };
    return labels[status];
  };

  return (
    <div className="min-h-screen bg-[#F9FAFB]">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-[1200px] mx-auto px-6 sm:px-12 lg:px-20 py-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-[#1E3A8A] flex items-center justify-center">
              <FileText className="w-6 h-6 text-white" />
            </div>
            <span className="text-xl font-semibold text-gray-900">DocQuality</span>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/')}
              className="hidden sm:flex px-4 py-2 border border-[#1E3A8A] text-[#1E3A8A] bg-white rounded-lg font-medium hover:bg-blue-50 transition-colors whitespace-nowrap text-sm print:hidden items-center"
            >
              Switch Workspace
            </button>
            <span className="text-sm text-gray-600 hidden sm:block print:hidden ml-2">AI Governance & Compliance Quality</span>
            {evaluationResult && (
              <div className="flex items-center gap-3">
                {!isHistoryView && (
                  <button
                    onClick={() => setIsHistoryOpen(true)}
                    className="hidden sm:flex px-4 py-2 border border-gray-300 text-gray-700 bg-white rounded-lg font-medium hover:bg-gray-50 items-center justify-center gap-2 transition-colors whitespace-nowrap text-sm print:hidden"
                  >
                    <Clock className="w-4 h-4" />
                    History
                  </button>
                )}
                <button
                  onClick={handleDownloadReport}
                  className="hidden sm:flex px-4 py-2 border border-gray-300 text-gray-700 bg-white rounded-lg font-medium hover:bg-gray-50 items-center justify-center gap-2 transition-colors whitespace-nowrap text-sm print:hidden"
                >
                  <Printer className="w-4 h-4" />
                  Print / Save PDF
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-[1200px] mx-auto px-6 sm:px-12 lg:px-20 py-12">
        {!evaluationResult ? (
          /* Upload State */
          <div className="flex flex-col items-center justify-center min-h-[calc(100vh-200px)]">
            <div className="text-center mb-12 px-4">
              <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-gray-900 mb-4">
                Document Quality Intelligence
              </h1>
              <p className="text-base sm:text-lg text-gray-600 max-w-2xl mx-auto">
                Upload a document to receive a structured quality and compliance analysis.
              </p>
            </div>

            <KnowledgeBasePanel
              workspace="compliance"
              apiPrefix="/compliance/api"
              accentColor="#1E3A8A"
              accentColorLight="#EFF6FF"
            />

            <UploadCard onFileSelect={handleFileSelect} selectedFile={selectedFile} />

            {/* Error Message */}
            {errorMessage && (
              <div className="mt-6 w-full max-w-[600px]">
                <AlertBox type="error" title="Evaluation Error">
                  {errorMessage}
                </AlertBox>
              </div>
            )}

            {isEvaluating ? (
              <div className="mt-8 w-full max-w-[500px] mx-auto">
                <div className="bg-white rounded-xl border border-gray-200 shadow-lg p-8">
                  <div className="flex items-center gap-3 mb-6">
                    <Loader2 className="w-6 h-6 text-[#1E3A8A] animate-spin" />
                    <p className="text-lg font-semibold text-gray-900">Analyzing your document...</p>
                  </div>
                  <EvaluationProgress />
                </div>
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
          /* Dashboard State */
          <div ref={dashboardRef} className="space-y-12 animate-in fade-in duration-500 bg-[#F9FAFB] pb-12">
            {/* Overall Score Card */}
            <div className="bg-white rounded-lg p-6 sm:p-8 shadow-md border border-gray-100">
              <div className="flex flex-col lg:flex-row items-center gap-8 lg:gap-12">
                <div className="flex-shrink-0">
                  <ScoreCircle score={Math.round(evaluationResult.overall_score)} />
                </div>
                <div className="flex-1 text-center lg:text-left">
                  <h2 className="text-2xl sm:text-3xl font-bold text-gray-900 mb-3">
                    Overall Document Quality Score
                  </h2>
                  <p className="text-sm sm:text-base text-gray-600 mb-4">
                    This score represents the aggregated evaluation across all defined data quality
                    dimensions.
                  </p>
                  <div className="flex flex-wrap items-center gap-3 mt-4">
                    <StatusBadge status={evaluationResult.overall_status}>
                      {getOverallStatusLabel(evaluationResult.overall_status)}
                    </StatusBadge>
                    {evaluationResult.filename && (
                      <div className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-50 border border-gray-200 max-w-[200px] sm:max-w-[300px]">
                        <FileText className="w-4 h-4 flex-shrink-0 text-gray-400" />
                        <span className="text-xs font-medium text-gray-500 uppercase tracking-wide hidden sm:inline">File</span>
                        <span className="text-xs text-gray-300 hidden sm:inline">|</span>
                        <span className="text-sm font-semibold text-gray-700 truncate" title={evaluationResult.filename}>
                          {evaluationResult.filename}
                        </span>
                      </div>
                    )}
                    {evaluationResult.document_type && evaluationResult.document_type !== 'unknown' && (
                      <div className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-[#1E3A8A]/5 to-[#1E3A8A]/10 border border-[#1E3A8A]/20">
                        <FileText className="w-4 h-4 text-[#1E3A8A]" />
                        <span className="text-xs font-medium text-gray-500 uppercase tracking-wide hidden sm:inline">Type</span>
                        <span className="text-xs text-gray-300 hidden sm:inline">|</span>
                        <span className="text-sm font-semibold text-[#1E3A8A] capitalize">{evaluationResult.document_type}</span>
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex flex-col sm:flex-row gap-3 mt-4 lg:mt-0 lg:ml-auto print:hidden">
                  <button
                    onClick={handleDownloadReport}
                    className="sm:hidden px-6 py-2 border border-gray-300 text-gray-700 bg-white rounded-lg font-medium hover:bg-gray-50 flex items-center justify-center gap-2 transition-colors whitespace-nowrap"
                  >
                    <Printer className="w-4 h-4" />
                    Print / Save PDF
                  </button>
                  <button
                    onClick={handleNewUpload}
                    className="px-6 py-2 border border-[#1E3A8A] text-[#1E3A8A] bg-white rounded-lg font-medium hover:bg-[#1E3A8A]/5 transition-colors whitespace-nowrap"
                  >
                    Upload New Document
                  </button>
                </div>
              </div>
            </div>

            {/* QUALITY DIMENSIONS Grid */}
            {(() => {
              const coreMetrics = evaluationResult.core_metrics || evaluationResult.metrics.filter(m => m.category === 'core');
              const specMetrics = evaluationResult.type_specific_metrics || [];
              const coreAvg = coreMetrics.length ? coreMetrics.reduce((sum, m) => sum + m.score, 0) / coreMetrics.length : 0;
              const specAvg = specMetrics.length ? specMetrics.reduce((sum, m) => sum + m.score, 0) / specMetrics.length : 0;
              
              const criticalCount = evaluationResult.issues.filter(i => i.severity === 'critical').length;
              const moderateCount = evaluationResult.issues.filter(i => i.severity === 'warning').length;
              
              const fmtDate = evaluationResult.created_at ? new Intl.DateTimeFormat('en-US', { month: 'long', day: 'numeric', year: 'numeric' }).format(new Date(evaluationResult.created_at.endsWith('Z') ? evaluationResult.created_at : `${evaluationResult.created_at}Z`)) : 'N/A';
              const displayId = evaluationResult.short_id ? `DOCQ-${(evaluationResult.created_at || "0000-00-00").substring(0,10).replace(/-/g,'')}-${evaluationResult.short_id}` : `ID-${(evaluationResult.evaluation_id || "PENDING").substring(0,6).toUpperCase()}`;

              return (
                <div className="mt-8">
                  <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-4">Quality Dimensions</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Tile 1: Document Integrity Score */}
                    <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-100 flex items-center gap-6">
                      <div className="w-20 h-20 sm:w-24 sm:h-24 shrink-0"><ScoreCircle score={Math.round(coreAvg)} disableAnimation size="sm" /></div>
                      <div>
                        <p className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-1">Document Integrity Score</p>
                        <p className="text-xs text-gray-400 mb-2">Based on universal quality metrics</p>
                        <StatusBadge status={getScoreColor(coreAvg).text.includes('#16A34A') ? 'good' : coreAvg >= 50 ? 'warning' : 'critical'}>
                          Quality Status
                        </StatusBadge>
                      </div>
                    </div>
                    {/* Tile 2: Domain-Specific Quality */}
                    <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-100 flex items-center gap-6">
                      {specMetrics.length > 0 ? (
                        <>
                          <div className="w-20 h-20 sm:w-24 sm:h-24 shrink-0"><ScoreCircle score={Math.round(specAvg)} disableAnimation size="sm" /></div>
                          <div>
                            <p className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-1">{(evaluationResult.semantic_type || 'Domain').replace(/_/g, ' ')} Quality</p>
                            <p className="text-xs text-gray-400 mb-2">Based on framework-specific standards</p>
                            <StatusBadge status={getScoreColor(specAvg).text.includes('#16A34A') ? 'good' : specAvg >= 50 ? 'warning' : 'critical'}>
                              Quality Status
                            </StatusBadge>
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="w-20 h-20 sm:w-24 sm:h-24 shrink-0 relative flex items-center justify-center">
                            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 160 160">
                              <circle cx="80" cy="80" r="70" stroke="currentColor" strokeWidth="10" fill="transparent" className="text-gray-100" />
                            </svg>
                            <span className="absolute text-xl font-bold text-gray-400">N/A</span>
                          </div>
                          <div>
                            <p className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-1">Domain-Specific Quality</p>
                            <p className="text-xs text-gray-400">No framework-specific ISO standards apply to this document type.</p>
                          </div>
                        </>
                      )}
                    </div>
                    {/* Tile 3: Issues Flagged */}
                    <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-100 flex items-center justify-between">
                      <div>
                        <p className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-2">Issues Flagged</p>
                        <div className="flex items-end gap-3 mb-2">
                          <span className="text-4xl font-bold text-gray-900">{evaluationResult.issues?.length || 0}</span>
                          <div className="flex flex-col mb-1 text-sm font-medium">
                            {criticalCount > 0 && <span className="text-red-600">{criticalCount} Critical</span>}
                            {moderateCount > 0 && <span className="text-yellow-600">{moderateCount} Moderate</span>}
                            {criticalCount === 0 && moderateCount === 0 && <span className="text-green-600">0 Issues</span>}
                          </div>
                        </div>
                        <p className="text-xs text-gray-400">Most affected: {(evaluationResult.issues && evaluationResult.issues.length > 0) ? (evaluationResult.issues[0].metric_name || 'General') : 'None'}</p>
                      </div>
                      <div className="w-12 h-12 bg-red-50 text-red-600 rounded-full flex items-center justify-center">
                         <AlertCircle className="w-6 h-6" />
                      </div>
                    </div>
                    {/* Tile 4: Review Information */}
                    <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-100">
                      <p className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-4">Review Information</p>
                      <div className="grid grid-cols-3 gap-y-3 gap-x-2 text-sm">
                        <span className="text-gray-400">Review Date:</span>
                        <span className="col-span-2 text-gray-900 font-medium">{fmtDate}</span>
                        <span className="text-gray-400">File:</span>
                        <span className="col-span-2 text-gray-900 font-medium truncate" title={evaluationResult.filename}>{evaluationResult.filename}</span>
                        <span className="text-gray-400">ID:</span>
                        <span className="col-span-2 font-mono text-gray-600 bg-gray-50 px-2 py-0.5 rounded w-max border border-gray-200">{displayId}</span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })()}

            {/* Executive Summary, Risk Assessment & Recommendations */}
            <ExecutiveSummary
              executiveSummary={evaluationResult.executive_summary}
              riskSummary={evaluationResult.risk_summary}
              recommendations={evaluationResult.recommendations}
              documentType={evaluationResult.document_type}
            />

            {/* Interactive Charts Section */}
            <div>
              <h2 className="text-2xl sm:text-3xl font-bold text-gray-900 mb-6">Visual Analytics</h2>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <MetricRadarChart
                  metrics={(evaluationResult.core_metrics || evaluationResult.metrics).map((m) => ({
                    name: m.name,
                    score: m.score,
                  }))}
                />
                <MetricBarChart
                  metrics={(evaluationResult.core_metrics || evaluationResult.metrics).map((m) => ({
                    name: m.name,
                    score: m.score,
                    status: m.status,
                  }))}
                  title="Core Metric Scores"
                />
              </div>
            </div>

            {/* Core Quality Metrics Grid */}
            <div>
              <h2 className="text-2xl sm:text-3xl font-bold text-gray-900 mb-6">Core Quality Metrics</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {(evaluationResult.core_metrics || evaluationResult.metrics.filter(m => m.category === 'core')).map((metric, index) => (
                  <div key={metric.id || metric.name} className="animate-in fade-in" style={{ animationDelay: `${index * 100}ms`, animationFillMode: 'backwards' }}>
                    <MetricCard {...mapMetricToCardProps(metric)} />
                  </div>
                ))}
              </div>
            </div>

            {/* Standards-Specific Metrics (non-collapsible, with empty state) */}
            <div>
              <div className="flex items-center gap-3 mb-6">
                <h2 className="text-2xl sm:text-3xl font-bold text-gray-900">Standards-Specific Metrics</h2>
                {evaluationResult.semantic_type && evaluationResult.semantic_type !== 'general' && (
                  <span className="px-3 py-1 rounded-lg bg-[#1E3A8A]/10 text-[#1E3A8A] text-xs font-semibold uppercase tracking-wider">
                    {evaluationResult.semantic_type.replace(/_/g, ' ')}
                  </span>
                )}
                {evaluationResult.type_specific_metrics && evaluationResult.type_specific_metrics.length > 0 && (
                  <span className="text-sm font-normal text-gray-500">({evaluationResult.type_specific_metrics.length} metrics)</span>
                )}
              </div>
              {evaluationResult.type_specific_metrics && evaluationResult.type_specific_metrics.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {evaluationResult.type_specific_metrics.map((metric, index) => (
                    <div key={metric.id || metric.name} className="animate-in fade-in" style={{ animationDelay: `${index * 100}ms`, animationFillMode: 'backwards' }}>
                      <MetricCard {...mapMetricToCardProps(metric)} />
                    </div>
                  ))}
                </div>
              ) : (
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
                  <p className="text-gray-500 text-sm">
                    Document classified as <span className="font-semibold text-gray-700 capitalize">{(evaluationResult.semantic_type || 'general').replace(/_/g, ' ')}</span>.
                    No framework-specific ISO standards apply to this document type.
                  </p>
                  <p className="text-gray-400 text-xs mt-2">
                    Upload an ISMS policy, privacy policy, or AI governance document to activate ISO 27001, 27701, or 42001 metrics.
                  </p>
                </div>
              )}
            </div>

            {/* Issues & Observations — full width */}
            <div className="mt-8">
              <IssuesTable issues={mapIssuesToTableProps(evaluationResult.issues)} />
            </div>

            {/* Pipeline Status */}
            {evaluationResult.pipeline_status && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mt-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Activity className="w-5 h-5 text-indigo-500" />
                  Data Engineering Pipeline
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
                  {Object.entries(evaluationResult.pipeline_status).map(([stage, status]) => (
                    <div key={stage} className="flex items-center gap-3 p-3 bg-gray-50 rounded-md border border-gray-100">
                      {status === 'success' ? (
                        <CheckCircle2 className="w-5 h-5 text-green-500 flex-shrink-0" />
                      ) : typeof status === 'number' ? (
                        <span className="w-5 h-5 flex items-center justify-center bg-blue-100 text-blue-700 text-xs font-bold rounded-full flex-shrink-0">{status}</span>
                      ) : (
                        <Circle className="w-5 h-5 text-gray-300 flex-shrink-0" />
                      )}
                      <div>
                        <p className="text-sm font-medium text-gray-700 capitalize">{stage}</p>
                        <p className="text-xs text-gray-500">{typeof status === 'number' ? 'Generated' : String(status)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Corrections Panel */}
            {correctionsData && correctionsData.total > 0 && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mt-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Wrench className="w-5 h-5 text-amber-500" />
                  Auto-Correction Proposals ({correctionsData.total})
                </h3>
                {isLoadingCorrections ? (
                  <div className="flex items-center justify-center p-8">
                    <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
                  </div>
                ) : (
                  <div className="space-y-6">
                    {Object.entries(correctionsData.grouped).map(([metricId, proposals]) => (
                      <div key={metricId} className="border border-gray-200 rounded-lg overflow-hidden">
                        <div className="bg-gray-50 px-4 py-3 border-b border-gray-200">
                          <h4 className="font-medium text-gray-800 tracking-wide text-sm">Metric Focus: {metricId}</h4>
                        </div>
                        <ul className="divide-y divide-gray-200">
                          {proposals.map(prop => (
                            <li key={prop.id} className="p-4 bg-white hover:bg-gray-50 transition-colors">
                              <div className="flex flex-col sm:flex-row items-start justify-between gap-4">
                                <div className="space-y-3 w-full">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest bg-gray-100 px-2 py-1 rounded">Target Field</span>
                                    <code className="text-sm font-mono text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100 break-all">{prop.field_path}</code>
                                    {prop.auto_applicable && (
                                      <span className="inline-flex items-center px-2 py-1 rounded text-[10px] font-bold tracking-widest uppercase bg-emerald-100 text-emerald-800 border border-emerald-200">
                                        Auto-Fix Available
                                      </span>
                                    )}
                                  </div>
                                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                    <div className="bg-red-50/50 p-3 rounded-lg border border-red-100 shadow-sm">
                                      <p className="text-xs text-red-700 font-bold mb-1.5 uppercase tracking-wider">Current Value</p>
                                      <p className="text-sm text-red-900 line-clamp-3 font-mono">{prop.current_value || 'null'}</p>
                                    </div>
                                    <div className="bg-green-50/50 p-3 rounded-lg border border-green-100 shadow-sm relative overflow-hidden">
                                      <div className="absolute top-0 right-0 w-16 h-16 bg-gradient-to-bl from-green-200 to-transparent opacity-50 pointer-events-none"></div>
                                      <p className="text-xs text-green-700 font-bold mb-1.5 uppercase tracking-wider">Proposed Value</p>
                                      <p className="text-sm text-green-900 line-clamp-3 font-mono">{prop.proposed_value}</p>
                                    </div>
                                  </div>
                                  <p className="text-sm text-gray-600 bg-gray-50 p-3 rounded border border-gray-100 italic">
                                    <span className="font-semibold not-italic mr-2">Reasoning:</span>
                                    {prop.reason}
                                  </p>
                                </div>
                                <div className="mt-2 sm:mt-0 flex flex-col items-center">
                                  {prop.applied ? (
                                    <span className="flex items-center gap-1.5 px-4 py-2 rounded-md bg-emerald-50 text-emerald-700 font-semibold border border-emerald-200">
                                      <CheckCircle2 className="w-5 h-5" /> Applied
                                    </span>
                                  ) : prop.auto_applicable ? (
                                    <button
                                      onClick={() => handleApplyFix(prop.id)}
                                      disabled={applyingFixId === prop.id}
                                      className={`px-4 py-2 rounded-md justify-center text-sm font-semibold whitespace-nowrap shadow-sm transition-all focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
                                        applyingFixId === prop.id 
                                        ? 'bg-blue-400 cursor-wait text-white' 
                                        : 'bg-blue-600 text-white hover:bg-blue-700'
                                      }`}
                                    >
                                      {applyingFixId === prop.id ? 'Applying...' : 'Apply Fix'}
                                    </button>
                                  ) : (
                                    <span className="px-4 py-2 rounded-md justify-center text-sm font-semibold whitespace-nowrap shadow-sm bg-orange-50 text-orange-700 border border-orange-200 pointer-events-none pb-2 text-center">
                                      Requires Manual Fix
                                    </span>
                                  )}
                                </div>
                              </div>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                    
                    {hasAppliedFixes && (
                      <div className="mt-8 pt-6 border-t border-gray-200 flex flex-col items-center justify-center p-6 bg-gradient-to-b from-transparent to-blue-50/50 rounded-b-xl">
                        <h4 className="text-lg font-bold text-gray-900 mb-2">Ready to download your fixed document?</h4>
                        <p className="text-sm text-gray-600 mb-6 text-center max-w-md">
                          We've applied the deterministic fixes directly to the extracted text. Download the updated version here. (Manual fixes still require side-by-side editing).
                        </p>
                        <a
                          href={`${API_BASE_URL}/api/evaluations/${evaluationResult.evaluation_id}/download-fixed`}
                          download
                          className="flex items-center gap-2 px-8 py-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-full font-semibold shadow-md hover:shadow-lg transition-all"
                        >
                          <Download className="w-5 h-5" />
                          Download Patched Document
                        </a>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 mt-24">
        <div className="max-w-[1200px] mx-auto px-6 sm:px-12 lg:px-20 py-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <span className="text-sm text-gray-500 font-medium">DocQuality ISO Compliance Engine</span>
          <span className="text-sm text-gray-500">Phase 2 — Data-Engineering Pipeline</span>
        </div>
      </footer>
      
      {isHistoryOpen && (
        <HistoryModal onClose={() => setIsHistoryOpen(false)} apiBaseUrl={API_BASE_URL} />
      )}
    </div>
  );
}