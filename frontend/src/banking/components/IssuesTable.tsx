import { useState, useMemo } from 'react';
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react';
import { StatusBadge } from './StatusBadge';

export interface Issue {
  fieldName: string;
  issueType: string;
  description: string;
  severity: 'good' | 'warning' | 'critical';
  regulationReference?: string;
  metricDimension?: string;
}

interface IssuesTableProps {
  issues: Issue[];
}

const SEVERITY_ORDER: Record<string, number> = { critical: 0, warning: 1, good: 2 };

const SEVERITY_LABELS: Record<string, string> = {
  good: 'Minor',
  warning: 'Moderate',
  critical: 'Critical',
};

type SortDir = 'asc' | 'desc' | 'none';

const ISSUE_TYPE_LABELS: Record<string, string> = {
  banking_metric_below_threshold: 'Metric below regulatory threshold',
  banking_metric_low: 'Metric quality below baseline',
};

function formatIssueType(issueType: string) {
  return ISSUE_TYPE_LABELS[issueType] || issueType;
}

export function IssuesTable({ issues }: IssuesTableProps) {
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [filterSeverity, setFilterSeverity] = useState<string>('all');
  const [filterDimension, setFilterDimension] = useState<string>('all');

  const dimensions = useMemo(() => {
    const all = issues.map((i) => i.metricDimension).filter(Boolean) as string[];
    return ['all', ...Array.from(new Set(all))];
  }, [issues]);

  const counts = useMemo(() => ({
    critical: issues.filter((i) => i.severity === 'critical').length,
    warning: issues.filter((i) => i.severity === 'warning').length,
    good: issues.filter((i) => i.severity === 'good').length,
  }), [issues]);

  const displayed = useMemo(() => {
    let filtered = issues;

    if (filterSeverity !== 'all') {
      filtered = filtered.filter((i) => i.severity === filterSeverity);
    }
    if (filterDimension !== 'all') {
      filtered = filtered.filter((i) => i.metricDimension === filterDimension);
    }

    if (sortDir !== 'none') {
      filtered = [...filtered].sort((a, b) => {
        const diff = SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity];
        return sortDir === 'desc' ? diff : -diff;
      });
    }

    return filtered;
  }, [issues, sortDir, filterSeverity, filterDimension]);

  const toggleSort = () => {
    setSortDir((prev) => (prev === 'desc' ? 'asc' : prev === 'asc' ? 'none' : 'desc'));
  };

  const SortIcon = sortDir === 'desc' ? ChevronDown : sortDir === 'asc' ? ChevronUp : ChevronsUpDown;

  if (issues.length === 0) {
    return (
      <div className="bg-white rounded-lg p-8 shadow-sm border border-gray-100">
        <h2 className="text-2xl font-semibold text-gray-900 mb-6">Issues & Observations</h2>
        <div className="flex flex-col items-center justify-center py-12">
          <div className="w-16 h-16 rounded-full bg-[#16A34A]/10 flex items-center justify-center mb-4">
            <svg className="w-8 h-8 text-[#16A34A]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <p className="text-lg font-medium text-gray-900">No issues detected</p>
          <p className="text-sm text-gray-500 mt-1">Document quality is high</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg p-6 sm:p-8 shadow-sm border border-gray-100">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-5">
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-2xl sm:text-3xl font-semibold text-gray-900">Issues & Observations</h2>
          {counts.critical > 0 && (
            <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700">
              {counts.critical} Critical
            </span>
          )}
          {counts.warning > 0 && (
            <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-yellow-100 text-yellow-700">
              {counts.warning} Moderate
            </span>
          )}
          {counts.good > 0 && (
            <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-700">
              {counts.good} Minor
            </span>
          )}
        </div>

        {/* Filters */}
        <div className="flex gap-2 flex-wrap">
          <select
            value={filterSeverity}
            onChange={(e) => setFilterSeverity(e.target.value)}
            className="text-xs border border-gray-200 rounded-md px-2 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-1 focus:ring-[#1E3A8A]"
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical</option>
            <option value="warning">Moderate</option>
            <option value="good">Minor</option>
          </select>

          {dimensions.length > 2 && (
            <select
              value={filterDimension}
              onChange={(e) => setFilterDimension(e.target.value)}
              className="text-xs border border-gray-200 rounded-md px-2 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-1 focus:ring-[#1E3A8A]"
            >
              {dimensions.map((d) => (
                <option key={d} value={d}>
                  {d === 'all' ? 'All Dimensions' : d}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto md:overflow-visible -mx-6 sm:mx-0">
        <div className="inline-block min-w-full align-middle px-6 sm:px-0">
          <table className="w-full min-w-[980px] table-fixed md:min-w-0">
            <colgroup>
              <col className="w-[19%]" />
              <col className="w-[17%]" />
              <col className="w-[36%]" />
              <col className="w-[16%]" />
              <col className="w-[12%]" />
            </colgroup>
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-3 sm:px-4 text-xs sm:text-sm font-semibold text-gray-700">Field</th>
                <th className="text-left py-3 px-3 sm:px-4 text-xs sm:text-sm font-semibold text-gray-700 whitespace-nowrap">Issue Type</th>
                <th className="text-left py-3 px-3 sm:px-4 text-xs sm:text-sm font-semibold text-gray-700">Description</th>
                <th className="text-left py-3 px-3 sm:px-4 text-xs sm:text-sm font-semibold text-gray-700 whitespace-nowrap">Regulation</th>
                <th
                  className="text-left py-3 px-3 sm:px-4 text-xs sm:text-sm font-semibold text-gray-700 whitespace-nowrap cursor-pointer select-none"
                  onClick={toggleSort}
                >
                  <span className="inline-flex items-center gap-1">
                    Severity
                    <SortIcon className="w-3.5 h-3.5" />
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              {displayed.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-sm text-gray-400">
                    No issues match the selected filters.
                  </td>
                </tr>
              ) : (
                displayed.map((issue, index) => (
                  <tr
                    key={index}
                    className={`border-b border-gray-100 hover:bg-gray-50 transition-colors ${
                      issue.severity === 'critical' ? 'bg-red-50/30' : ''
                    }`}
                  >
                    <td className="py-4 px-3 sm:px-4 text-sm font-medium leading-6 text-gray-900 break-words whitespace-normal align-top">
                      {issue.fieldName}
                      {issue.metricDimension && (
                        <div className="mt-1 text-xs font-normal text-gray-400 break-words">{issue.metricDimension}</div>
                      )}
                    </td>
                    <td className="py-4 px-3 sm:px-4 text-xs sm:text-sm text-gray-700 whitespace-normal break-words align-top">
                      {formatIssueType(issue.issueType)}
                    </td>
                    <td className="py-4 px-3 sm:px-4 text-[15px] leading-7 text-gray-700 break-words whitespace-normal align-top">{issue.description}</td>
                    <td className="py-4 px-3 sm:px-4 align-top whitespace-normal break-words">
                      {issue.regulationReference ? (
                        <span className="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
                          {issue.regulationReference}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-300">—</span>
                      )}
                    </td>
                    <td className="py-4 px-3 sm:px-4 align-top">
                      <StatusBadge status={issue.severity}>
                        {SEVERITY_LABELS[issue.severity]}
                      </StatusBadge>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}