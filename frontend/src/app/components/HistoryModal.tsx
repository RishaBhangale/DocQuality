import { useState, useEffect } from 'react';
import { X, Clock, FileText, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';

interface EvaluationSummary {
  evaluation_id: string;
  short_id: string | null;
  filename: string;
  overall_score: number;
  overall_status: string;
  created_at: string;
}

interface GroupedEvaluations {
  [filename: string]: EvaluationSummary[];
}

interface HistoryModalProps {
  onClose: () => void;
  apiBaseUrl: string;
}

export function HistoryModal({ onClose, apiBaseUrl }: HistoryModalProps) {
  const [evaluations, setEvaluations] = useState<EvaluationSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedFiles, setExpandedFiles] = useState<{ [filename: string]: boolean }>({});

  useEffect(() => {
    setIsLoading(true);
    fetch(`${apiBaseUrl}/api/evaluations`)
      .then(res => {
        if (!res.ok) throw new Error('Failed to fetch history');
        return res.json();
      })
      .then(data => setEvaluations(data))
      .catch(err => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [apiBaseUrl]);

  // Group by filename
  const grouped: GroupedEvaluations = {};
  for (const ev of evaluations) {
    if (!grouped[ev.filename]) grouped[ev.filename] = [];
    grouped[ev.filename].push(ev);
  }

  const toggleExpand = (filename: string) => {
    setExpandedFiles(prev => ({ ...prev, [filename]: !prev[filename] }));
  };

  const handleOpenReport = (id: string) => {
    window.open(`/?id=${id}`, '_blank');
  };

  const formatDate = (isoString: string) => {
    const utcString = isoString.endsWith('Z') ? isoString : `${isoString}Z`;
    const d = new Date(utcString);
    return new Intl.DateTimeFormat('en-US', {
      month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit'
    }).format(d);
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600 bg-green-50 border-green-200';
    if (score >= 50) return 'text-yellow-600 bg-yellow-50 border-yellow-200';
    return 'text-red-600 bg-red-50 border-red-200';
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-gray-900/50 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-gray-50/50">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 text-blue-700 rounded-lg">
              <Clock className="w-5 h-5" />
            </div>
            <h2 className="text-lg font-bold text-gray-900">Analysis Lineage</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-full transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-12 text-gray-400">
              <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-4" />
              <p>Loading document history...</p>
            </div>
          ) : error ? (
            <div className="p-4 bg-red-50 text-red-700 rounded-lg text-sm">
              <p className="font-semibold mb-1">Error Loading History</p>
              {error}
            </div>
          ) : Object.keys(grouped).length === 0 ? (
            <div className="text-center py-12">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <FileText className="w-8 h-8 text-gray-400" />
              </div>
              <h3 className="text-gray-900 font-medium mb-1">No Analyses Yet</h3>
              <p className="text-sm text-gray-500">Upload a document to see its history here.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {Object.entries(grouped).map(([filename, evs]) => {
                const isExpanded = expandedFiles[filename];
                const latest = evs[0]; // evaluations are order by desc usually

                return (
                  <div key={filename} className="border border-gray-200 rounded-lg overflow-hidden bg-white hover:border-blue-300 transition-colors">
                    {/* Parent Row */}
                    <div 
                      className={`flex items-center justify-between p-4 cursor-pointer select-none transition-colors ${isExpanded ? 'bg-blue-50/50' : 'hover:bg-gray-50'}`}
                      onClick={() => toggleExpand(filename)}
                    >
                      <div className="flex items-center gap-3 min-w-0 flex-1">
                        <FileText className="w-5 h-5 text-gray-400 flex-shrink-0" />
                        <div className="min-w-0">
                          <p className="font-semibold text-gray-900 truncate" title={filename}>{filename}</p>
                          <p className="text-xs text-gray-500 mt-0.5">Last analysis: {formatDate(latest.created_at)}</p>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-4 ml-4 flex-shrink-0">
                        <span className="inline-flex items-center justify-center px-2.5 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-600 border border-gray-200">
                          {evs.length} Iteration{evs.length !== 1 && 's'}
                        </span>
                        <div className="w-6 h-6 flex items-center justify-center text-gray-400">
                           {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                        </div>
                      </div>
                    </div>

                    {/* Expanded Lineage */}
                    {isExpanded && (
                      <div className="bg-gray-50 border-t border-gray-100 p-4 pl-[3.25rem]">
                        <div className="relative before:absolute before:inset-y-0 before:left-[-1.25rem] before:w-px before:bg-gray-300">
                          <div className="space-y-3">
                            {evs.map((ev, idx) => (
                              <div key={ev.evaluation_id} className="relative flex items-center justify-between bg-white p-3 rounded-lg border border-gray-200 shadow-sm group">
                                {/* Timeline connecting dot */}
                                <div className="absolute left-[-1.53rem] top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-blue-500 border-2 border-white ring-1 ring-gray-200" />
                                
                                <div className="flex items-center gap-4">
                                  <div className={`flex flex-col items-center justify-center w-12 h-12 rounded border ${getScoreColor(ev.overall_score)}`}>
                                    <span className="text-sm font-bold tracking-tighter">{Math.round(ev.overall_score)}</span>
                                  </div>
                                  <div>
                                    <div className="flex items-center gap-2">
                                      <span className="text-sm font-semibold text-gray-900 truncate max-w-[150px] sm:max-w-xs">{formatDate(ev.created_at)}</span>
                                      {idx === 0 && <span className="px-1.5 rounded bg-blue-100 text-blue-700 text-[10px] uppercase font-bold tracking-wider">Latest</span>}
                                    </div>
                                    <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                                      <span className="font-mono bg-gray-100 px-1.5 rounded text-gray-600">ID: {ev.short_id || ev.evaluation_id.substring(0,8)}</span>
                                      <span className="capitalize text-gray-400">• {(ev.overall_status || 'evaluated').replace('_', ' ')}</span>
                                    </div>
                                  </div>
                                </div>
                                
                                <a
                                  href={`/?id=${ev.evaluation_id}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  onClick={(e) => e.stopPropagation()}
                                  className="w-8 h-8 flex items-center justify-center rounded-lg text-blue-600 hover:bg-blue-50 hover:text-blue-700 transition-colors ml-2"
                                  title="Open Report in New Tab"
                                >
                                  <ExternalLink className="w-4 h-4" />
                                </a>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
        
        {/* Footer */}
        <div className="flex justify-end p-4 border-t border-gray-100 bg-gray-50 shrink-0">
          <button
            onClick={onClose}
            className="px-5 py-2 bg-white border border-gray-300 rounded-lg text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
