interface StatusBadgeProps {
  status: 'good' | 'warning' | 'critical';
  children: React.ReactNode;
}

export function StatusBadge({ status, children }: StatusBadgeProps) {
  const styles = {
    good: 'bg-[#16A34A]/10 text-[#16A34A] border-[#16A34A]/20',
    warning: 'bg-[#EAB308]/10 text-[#CA8A04] border-[#EAB308]/20',
    critical: 'bg-[#DC2626]/10 text-[#DC2626] border-[#DC2626]/20',
  };

  return (
    <span className={`inline-flex items-center px-2.5 sm:px-3 py-1 rounded-md border ${styles[status]}`}>
      <span className="text-xs sm:text-sm font-medium">{children}</span>
    </span>
  );
}