import { StatusBadge } from './StatusBadge';

interface Issue {
  fieldName: string;
  issueType: string;
  description: string;
  severity: 'good' | 'warning' | 'critical';
  metricName?: string;
}

interface IssuesTableProps {
  issues: Issue[];
}

export function IssuesTable({ issues }: IssuesTableProps) {
  const severityLabels = {
    good: 'Minor',
    warning: 'Moderate',
    critical: 'Critical',
  };

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
      <h2 className="text-2xl sm:text-3xl font-semibold text-gray-900 mb-6">Issues & Observations</h2>
      <div className="overflow-x-auto -mx-6 sm:mx-0">
        <div className="inline-block min-w-full align-middle px-6 sm:px-0">
          <table className="min-w-full table-fixed">
            <colgroup>
              <col style={{ width: '20%' }} />
              <col style={{ width: '15%' }} />
              <col style={{ width: '15%' }} />
              <col style={{ width: '35%' }} />
              <col style={{ width: '15%' }} />
            </colgroup>
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-3 sm:px-4 text-xs sm:text-sm font-semibold text-gray-700">Field Name</th>
                <th className="text-left py-3 px-3 sm:px-4 text-xs sm:text-sm font-semibold text-gray-700">Metric</th>
                <th className="text-left py-3 px-3 sm:px-4 text-xs sm:text-sm font-semibold text-gray-700">Issue Type</th>
                <th className="text-left py-3 px-3 sm:px-4 text-xs sm:text-sm font-semibold text-gray-700">Description</th>
                <th className="text-left py-3 px-3 sm:px-4 text-xs sm:text-sm font-semibold text-gray-700">Severity</th>
              </tr>
            </thead>
            <tbody>
              {issues.map((issue, index) => (
                <tr key={index} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                  <td className="py-4 px-3 sm:px-4 text-xs sm:text-sm font-medium text-gray-900 break-words">{issue.fieldName}</td>
                  <td className="py-4 px-3 sm:px-4 text-xs sm:text-sm text-[#1E3A8A] font-medium break-words">{issue.metricName || 'Other'}</td>
                  <td className="py-4 px-3 sm:px-4 text-xs sm:text-sm text-gray-600 break-words">{issue.issueType}</td>
                  <td className="py-4 px-3 sm:px-4 text-xs sm:text-sm text-gray-600 break-words">{issue.description}</td>
                  <td className="py-4 px-3 sm:px-4">
                    <StatusBadge status={issue.severity}>
                      {severityLabels[issue.severity]}
                    </StatusBadge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}