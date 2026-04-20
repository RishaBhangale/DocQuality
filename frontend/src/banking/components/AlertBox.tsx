import { AlertCircle, CheckCircle2, AlertTriangle } from 'lucide-react';

interface AlertBoxProps {
  type: 'success' | 'error' | 'warning';
  title?: string;
  children: React.ReactNode;
}

export function AlertBox({ type, title, children }: AlertBoxProps) {
  const styles = {
    success: {
      container: 'bg-[#16A34A]/10 border-[#16A34A]/20 text-[#16A34A]',
      icon: CheckCircle2,
    },
    error: {
      container: 'bg-[#DC2626]/10 border-[#DC2626]/20 text-[#DC2626]',
      icon: AlertCircle,
    },
    warning: {
      container: 'bg-[#EAB308]/10 border-[#EAB308]/20 text-[#CA8A04]',
      icon: AlertTriangle,
    },
  };

  const Icon = styles[type].icon;

  return (
    <div className={`rounded-lg border p-4 ${styles[type].container}`}>
      <div className="flex gap-3">
        <Icon className="w-5 h-5 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          {title && <h3 className="font-semibold mb-1">{title}</h3>}
          <div className="text-sm">{children}</div>
        </div>
      </div>
    </div>
  );
}
