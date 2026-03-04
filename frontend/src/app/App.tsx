import { useState, useRef } from 'react';
import { Loader2, FileText, Download, Printer } from 'lucide-react';
import { UploadCard } from './components/UploadCard';
import { ScoreCircle } from './components/ScoreCircle';
import { MetricCard } from './components/MetricCard';
import { IssuesTable } from './components/IssuesTable';
import { StatusBadge } from './components/StatusBadge';
import { MetricRadarChart } from './components/MetricRadarChart';
import { MetricBarChart } from './components/MetricBarChart';
import { SeverityPieChart } from './components/SeverityPieChart';
import { ExecutiveSummary } from './components/ExecutiveSummary';
import { AlertBox } from './components/AlertBox';
import { TypeSpecificMetrics } from './components/TypeSpecificMetrics';

// --- Types matching backend API response ---

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
}

interface TypeSpecificMetric {
  name: string;
  score: number;
  description: string;
  status: 'good' | 'warning' | 'critical';
  details: string;
  document_type: string;
}

interface EvaluationResult {
  evaluation_id: string;
  filename: string;
  document_type: string;
  overall_score: number;
  overall_status: 'good' | 'warning' | 'critical';
  metrics: Metric[];
  type_specific_metrics: TypeSpecificMetric[];
  type_specific_score: number | null;
  issues: Issue[];
  executive_summary: string;
  risk_summary: string;
  recommendations: string[];
  created_at: string;
}

// --- API Configuration ---

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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

const METRIC_EXPLANATIONS: Record<string, string> = {
  'Completeness': 'Measures whether all required structured fields are present in the document. This ensures that no critical information is missing from the data extraction process.',
  'Accuracy': 'Evaluates extracted data against validation logic and known constraints. This verifies that the extracted values are correct and match expected patterns or ranges.',
  'Consistency': 'Checks logical relationships between fields to ensure they align correctly. For example, line items should sum to the total amount, or dates should follow a logical sequence.',
  'Validity': 'Ensures values conform to expected formats and standards. This includes checking email formats, phone numbers, postal codes, and other structured data types.',
  'Timeliness': 'Assesses the recency of time-sensitive fields. This is particularly important for documents with expiration dates or time-bound information.',
  'Uniqueness': 'Identifies duplicate structured entries or data points. This helps prevent data redundancy and ensures each piece of information is unique within the document.',
};

function mapMetricToCardProps(m: Metric) {
  return {
    name: m.name,
    score: m.score,
    description: m.description,
    statusMessage: m.status_message,
    status: m.status,
    explanation: METRIC_EXPLANATIONS[m.name] || '',
    issueDetails: m.reasoning,
  };
}

function mapIssuesToTableProps(issues: Issue[]) {
  return issues.map((i) => ({
    fieldName: i.field_name,
    issueType: i.issue_type,
    description: i.description,
    severity: i.severity,
  }));
}

export default function App() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [evaluationResult, setEvaluationResult] = useState<EvaluationResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

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
            <span className="text-sm text-gray-600 hidden sm:block print:hidden">Unstructured Data Quality</span>
            {evaluationResult && (
              <button
                onClick={handleDownloadReport}
                className="hidden sm:flex px-4 py-2 border border-gray-300 text-gray-700 bg-white rounded-lg font-medium hover:bg-gray-50 items-center justify-center gap-2 transition-colors whitespace-nowrap text-sm print:hidden"
              >
                <Printer className="w-4 h-4" />
                Print / Save PDF
              </button>
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
                Upload a document to receive a structured quality analysis across completeness,
                accuracy, consistency, validity, timeliness, and uniqueness.
              </p>
            </div>

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
              <div className="mt-8 flex flex-col items-center">
                <Loader2 className="w-10 h-10 text-[#1E3A8A] animate-spin mb-4" />
                <p className="text-lg font-medium text-gray-900">Analyzing document quality...</p>
                <p className="text-sm text-gray-500 mt-1">This may take a few seconds</p>
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

            {/* Executive Summary, Risk Assessment & Recommendations */}
            <ExecutiveSummary
              executiveSummary={evaluationResult.executive_summary}
              riskSummary={evaluationResult.risk_summary}
              recommendations={evaluationResult.recommendations}
              documentType={evaluationResult.document_type}
            />

            {/* Interactive Charts Section — Core Metrics */}
            <div>
              <h2 className="text-2xl sm:text-3xl font-bold text-gray-900 mb-6">Visual Analytics</h2>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <MetricRadarChart
                  metrics={evaluationResult.metrics.map((m) => ({
                    name: m.name,
                    score: m.score,
                  }))}
                />
                <MetricBarChart
                  metrics={evaluationResult.metrics.map((m) => ({
                    name: m.name,
                    score: m.score,
                    status: m.status,
                  }))}
                  title="Core Metric Scores"
                />
              </div>

              {/* Type-Specific Metrics Chart */}
              {evaluationResult.type_specific_metrics && evaluationResult.type_specific_metrics.length > 0 && (
                <div className="mt-6">
                  <MetricBarChart
                    metrics={evaluationResult.type_specific_metrics.map((m) => ({
                      name: m.name,
                      score: m.score,
                      status: m.status,
                    }))}
                    title={`${evaluationResult.document_type} — Type-Specific Scores`}
                  />
                </div>
              )}
            </div>

            {/* Metrics Grid */}
            <div>
              <h2 className="text-2xl sm:text-3xl font-bold text-gray-900 mb-6">Quality Breakdown</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {evaluationResult.metrics.map((metric, index) => (
                  <div
                    key={metric.name}
                    className="animate-in fade-in"
                    style={{
                      animationDelay: `${index * 100}ms`,
                      animationFillMode: 'backwards',
                    }}
                  >
                    <MetricCard {...mapMetricToCardProps(metric)} />
                  </div>
                ))}
              </div>
            </div>

            {/* Document-Specific Metrics (right after core breakdown) */}
            {evaluationResult.type_specific_metrics && evaluationResult.type_specific_metrics.length > 0 && (
              <TypeSpecificMetrics
                metrics={evaluationResult.type_specific_metrics}
                documentType={evaluationResult.document_type}
                typeSpecificScore={evaluationResult.type_specific_score}
                filename={evaluationResult.filename}
              />
            )}

            {/* Issues + Severity Distribution */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2">
                <IssuesTable issues={mapIssuesToTableProps(evaluationResult.issues)} />
              </div>
              <div>
                <SeverityPieChart issues={mapIssuesToTableProps(evaluationResult.issues)} />
              </div>
            </div>


          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 mt-24">
        <div className="max-w-[1200px] mx-auto px-6 sm:px-12 lg:px-20 py-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <span className="text-sm text-gray-500">Document Quality Engine v1.0</span>
          <span className="text-sm text-gray-500">Powered by AI-assisted evaluation</span>
        </div>
      </footer>
    </div>
  );
}