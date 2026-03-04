import { FileText, AlertTriangle, CheckCircle, XCircle, ChevronRight, X } from 'lucide-react';
import * as Dialog from '@radix-ui/react-dialog';

interface TypeSpecificMetric {
    name: string;
    score: number;
    description: string;
    status: 'good' | 'warning' | 'critical';
    details: string;
    document_type: string;
}

interface TypeSpecificMetricsProps {
    metrics: TypeSpecificMetric[];
    documentType: string;
    typeSpecificScore?: number | null;
    filename?: string;
}

const STATUS_COLORS = {
    good: { bg: 'bg-[#DCFCE7]', text: '#16A34A', border: 'border-[#16A34A]/20', textColorClass: 'text-[#16A34A]' },
    warning: { bg: 'bg-[#FEF3C7]', text: '#D97706', border: 'border-[#EAB308]/20', textColorClass: 'text-[#D97706]' },
    critical: { bg: 'bg-[#FEE2E2]', text: '#DC2626', border: 'border-[#DC2626]/20', textColorClass: 'text-[#DC2626]' },
};

const DOC_TYPE_LABELS: Record<string, string> = {
    contract: 'Contract Analysis',
    invoice: 'Invoice Analysis',
    json: 'JSON Data Analysis',
    json_document: 'JSON Data Analysis',
    social_media: 'Social Media Analysis',
    tabular: 'Tabular Data Analysis',
    markup: 'Structured Markup Analysis',
    email: 'Email Analysis',
    general: 'General Document Analysis',
};

function StatusIcon({ status }: { status: string }) {
    if (status === 'good') return <CheckCircle className="w-5 h-5 text-green-600" />;
    if (status === 'warning') return <AlertTriangle className="w-5 h-5 text-yellow-600" />;
    return <XCircle className="w-5 h-5 text-red-600" />;
}

export function TypeSpecificMetrics({ metrics, documentType, typeSpecificScore, filename }: TypeSpecificMetricsProps) {
    if (!metrics || metrics.length === 0) return null;

    const label = DOC_TYPE_LABELS[documentType.toLowerCase()] || `${documentType} Analysis`;

    return (
        <div>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-4">
                <h2 className="text-2xl sm:text-3xl font-bold text-gray-900 flex flex-wrap items-center gap-3">
                    Document-Specific Analysis
                    {filename && (
                        <span className="text-base sm:text-lg font-normal text-gray-500 bg-gray-100 px-3 py-1 rounded-md border border-gray-200">
                            {filename}
                        </span>
                    )}
                </h2>
                {typeSpecificScore !== null && typeSpecificScore !== undefined && (
                    <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#1E3A8A]/5 border border-[#1E3A8A]/20 whitespace-nowrap">
                        <span className="text-sm font-medium text-gray-500">Type Score</span>
                        <span className="text-lg font-bold text-[#1E3A8A]">
                            {Math.round(typeSpecificScore)}/100
                        </span>
                    </div>
                )}
            </div>

            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-[#1E3A8A]/5 to-[#1E3A8A]/10 border border-[#1E3A8A]/20 mb-6">
                <FileText className="w-4 h-4 text-[#1E3A8A]" />
                <span className="text-sm font-semibold text-[#1E3A8A]">{label}</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {metrics.map((metric) => {
                    const colors = STATUS_COLORS[metric.status] || STATUS_COLORS.good;

                    return (
                        <Dialog.Root key={metric.name}>
                            <Dialog.Trigger asChild>
                                <div className="bg-white rounded-lg p-5 shadow-sm border border-gray-100 hover:shadow-lg hover:-translate-y-1 transition-all duration-200 cursor-pointer group text-left h-full flex flex-col">
                                    <div className="flex items-start justify-between mb-3">
                                        <div className="flex items-center gap-2">
                                            <StatusIcon status={metric.status} />
                                            <h3 className="text-base font-semibold text-gray-900 group-hover:text-[#1E3A8A] transition-colors">{metric.name}</h3>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span
                                                className="text-lg font-bold"
                                                style={{ color: colors.text }}
                                            >
                                                {Math.round(metric.score)}%
                                            </span>
                                            <ChevronRight className="w-5 h-5 text-gray-300 group-hover:text-[#1E3A8A] transition-colors" />
                                        </div>
                                    </div>

                                    {/* Score bar */}
                                    <div className="w-full h-2 bg-gray-100 rounded-full mb-3">
                                        <div
                                            className="h-full rounded-full transition-all duration-500"
                                            style={{
                                                width: `${metric.score}%`,
                                                backgroundColor: colors.text,
                                            }}
                                        />
                                    </div>

                                    <p className="text-sm text-gray-600 line-clamp-2">{metric.description}</p>
                                </div>
                            </Dialog.Trigger>

                            <Dialog.Portal>
                                <Dialog.Overlay className="fixed inset-0 bg-black/40 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 z-50" />
                                <Dialog.Content className="fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-6 border bg-white p-8 shadow-2xl duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%] sm:rounded-2xl">

                                    <div className="flex flex-col gap-2">
                                        <div className="flex items-start justify-between">
                                            <div className="flex items-center gap-3">
                                                <StatusIcon status={metric.status} />
                                                <Dialog.Title className="text-2xl font-bold text-gray-900">
                                                    {metric.name}
                                                </Dialog.Title>
                                            </div>
                                            <Dialog.Close className="rounded-full p-1.5 hover:bg-gray-100 transition-colors focus:outline-none focus:ring-2 focus:ring-[#1E3A8A] ring-offset-2">
                                                <X className="h-5 w-5 text-gray-500" />
                                                <span className="sr-only">Close</span>
                                            </Dialog.Close>
                                        </div>

                                        <div className="flex items-center gap-3 mt-2">
                                            <span className={`px-3 py-1 rounded-md text-base font-bold ${colors.bg} ${colors.textColorClass}`}>
                                                Score: {Math.round(metric.score)}%
                                            </span>
                                        </div>
                                    </div>

                                    <div className="flex flex-col gap-6">
                                        {/* Description */}
                                        <div>
                                            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Metric Overview</h4>
                                            <p className="text-sm text-gray-700 leading-relaxed">
                                                {metric.description}
                                            </p>
                                        </div>

                                        {/* Issue Details / Findings */}
                                        {metric.details && (
                                            <div className={`p-4 rounded-xl border ${colors.bg} ${colors.border}`}>
                                                <h4 className={`text-xs font-semibold uppercase tracking-wider mb-2 ${colors.textColorClass}`}>
                                                    Analysis Findings
                                                </h4>
                                                <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
                                                    {metric.details}
                                                </p>
                                            </div>
                                        )}
                                    </div>

                                </Dialog.Content>
                            </Dialog.Portal>
                        </Dialog.Root>
                    );
                })}
            </div>
        </div>
    );
}
