type Severity = 'good' | 'warning' | 'critical';

function normalizeStatus(raw: string): Severity {
  const s = (raw || '').toLowerCase();
  if (s === 'good' || s === 'pass' || s === 'passed') return 'good';
  if (s === 'warning' || s === 'review' || s === 'moderate') return 'warning';
  return 'critical';
}

interface StatusBadgeProps {
  status: string;
  children?: React.ReactNode;
}

const DEFAULT_LABELS: Record<Severity, string> = {
  good: 'Meets quality standards',
  warning: 'Review recommended',
  critical: 'Critical issues detected',
};

export function StatusBadge({ status, children }: StatusBadgeProps) {
  const key = normalizeStatus(status);
  const styles: Record<Severity, string> = {
    good: 'bg-[#16A34A]/10 text-[#16A34A] border-[#16A34A]/20',
    warning: 'bg-[#EAB308]/10 text-[#CA8A04] border-[#EAB308]/20',
    critical: 'bg-[#DC2626]/10 text-[#DC2626] border-[#DC2626]/20',
  };

  return (
    <span className={`inline-flex items-center px-2.5 sm:px-3 py-1 rounded-md border ${styles[key]}`}>
      <span className="text-xs sm:text-sm font-medium">{children ?? DEFAULT_LABELS[key]}</span>
    </span>
  );
}