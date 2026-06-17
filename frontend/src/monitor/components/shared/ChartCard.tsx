import type { ReactNode } from 'react'

interface ChartCardProps {
  title: string
  subtitle?: string
  children: ReactNode
  className?: string
  action?: ReactNode
}

export function ChartCard({ title, subtitle, children, className = '', action }: ChartCardProps) {
  return (
    <div className={`glass-card rounded-2xl p-5 flex flex-col gap-4 ${className}`}>
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-text-primary text-sm font-semibold">{title}</h3>
          {subtitle && (
            <p className="text-text-muted text-xs mt-0.5">{subtitle}</p>
          )}
        </div>
        {action && <div>{action}</div>}
      </div>
      <div className="flex-1 min-h-0">{children}</div>
    </div>
  )
}
