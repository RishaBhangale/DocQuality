import { ProgressBar } from './ProgressBar';

interface MetricCardProps {
  name: string;
  score: number;
  description: string;
  statusMessage: string;
  status: 'good' | 'warning' | 'critical';
}

export function MetricCard({ name, score, description, statusMessage, status }: MetricCardProps) {
  const statusColors = {
    good: 'text-[#16A34A]',
    warning: 'text-[#CA8A04]',
    critical: 'text-[#DC2626]',
  };

  const statusBgColors = {
    good: 'bg-[#16A34A]/10',
    warning: 'bg-[#EAB308]/10',
    critical: 'bg-[#DC2626]/10',
  };

  return (
    <div className="bg-white rounded-lg p-6 shadow-sm hover:shadow-lg border border-gray-100 transition-all duration-200">
      <div className="flex items-start justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">{name}</h3>
        <span className={`px-3 py-1 rounded-md text-sm font-semibold ${statusBgColors[status]} ${statusColors[status]}`}>
          {score}%
        </span>
      </div>
      
      <div className="mb-4">
        <ProgressBar value={score} status={status} />
      </div>
      
      <p className="text-sm text-gray-600 mb-3">
        {description}
      </p>
      
      <p className={`text-sm font-medium ${statusColors[status]}`}>
        {statusMessage}
      </p>
    </div>
  );
}