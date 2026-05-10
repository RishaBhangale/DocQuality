interface ProgressBarProps {
  value: number;
  status: 'good' | 'warning' | 'critical';
}

export function ProgressBar({ value, status }: ProgressBarProps) {
  const colors = {
    good: '#16A34A',
    warning: '#EAB308',
    critical: '#DC2626',
  };

  return (
    <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
      <div
        className="h-full transition-all duration-500 ease-out rounded-full"
        style={{
          width: `${value}%`,
          backgroundColor: colors[status],
        }}
      />
    </div>
  );
}
