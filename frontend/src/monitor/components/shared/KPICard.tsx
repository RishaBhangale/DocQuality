import { useEffect, useRef, useState } from 'react'
import { TrendingUp, TrendingDown, Minus, Info, X } from 'lucide-react'

interface KPICardProps {
  title: string
  value: number
  format: 'number' | 'percent' | 'ms' | 'currency'
  subtitle?: string
  trend?: 'up' | 'down' | 'neutral'
  trendValue?: string
  icon?: React.ReactNode
  accentColor?: string
  description?: string   // Explanation of how this metric is calculated
}

function formatValue(value: number, format: KPICardProps['format']): string {
  switch (format) {
    case 'percent':
      return `${value.toFixed(1)}%`
    case 'ms':
      return value >= 1000 ? `${(value / 1000).toFixed(2)}s` : `${Math.round(value)}ms`
    case 'currency':
      return `$${value.toFixed(2)}`
    case 'number':
    default:
      return value >= 1_000_000
        ? `${(value / 1_000_000).toFixed(1)}M`
        : value >= 1_000
          ? `${(value / 1_000).toFixed(1)}K`
          : value % 1 === 0
            ? value.toLocaleString()
            : value.toFixed(2)
  }
}

export function KPICard({
  title,
  value,
  format,
  subtitle,
  trend,
  trendValue,
  icon,
  accentColor = '#2563EB',
  description,
}: KPICardProps) {
  const [displayValue, setDisplayValue] = useState(0)
  const [showInfo, setShowInfo] = useState(false)
  const animRef = useRef<number | null>(null)
  const prevValueRef = useRef(0)
  const popoverRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const start = prevValueRef.current
    const end = value
    const duration = 800
    const startTime = performance.now()

    const animate = (now: number) => {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setDisplayValue(start + (end - start) * eased)
      if (progress < 1) {
        animRef.current = requestAnimationFrame(animate)
      } else {
        prevValueRef.current = end
      }
    }

    animRef.current = requestAnimationFrame(animate)
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current)
    }
  }, [value])

  // Close popover on outside click
  useEffect(() => {
    if (!showInfo) return
    const handler = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setShowInfo(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showInfo])

  const trendIcon =
    trend === 'up'   ? <TrendingUp size={14} /> :
    trend === 'down' ? <TrendingDown size={14} /> :
    <Minus size={14} />

  const trendColor =
    trend === 'up'   ? 'text-accent-green' :
    trend === 'down' ? 'text-accent-red' :
    'text-text-muted'

  return (
    <div className="glass-card rounded-2xl p-5 flex flex-col gap-3 relative overflow-visible group transition-all duration-300">
      {/* Accent glow line */}
      <div
        className="absolute top-0 left-0 right-0 h-[2px] opacity-50 group-hover:opacity-80 transition-opacity rounded-t-2xl"
        style={{ background: `linear-gradient(90deg, transparent, ${accentColor}, transparent)` }}
      />

      <div className="flex items-center justify-between">
        <span className="text-text-secondary text-xs font-medium uppercase tracking-wider">
          {title}
        </span>
        <div className="flex items-center gap-2">
          {icon && (
            <span className="text-text-muted" style={{ color: accentColor }}>
              {icon}
            </span>
          )}
          {description && (
            <button
              onClick={() => setShowInfo(!showInfo)}
              className="text-text-muted hover:text-accent-cyan transition-colors rounded-full p-0.5"
              title="Learn how this is calculated"
            >
              <Info size={13} />
            </button>
          )}
        </div>
      </div>

      <div className="animate-count-up">
        <span className="text-3xl xl:text-4xl font-bold text-text-primary tracking-tight">
          {formatValue(displayValue, format)}
        </span>
      </div>

      <div className="flex items-center justify-between">
        {subtitle && (
          <span className="text-text-muted text-xs">{subtitle}</span>
        )}
        {trend && trendValue && (
          <span className={`flex items-center gap-1 text-xs font-medium ${trendColor}`}>
            {trendIcon}
            {trendValue}
          </span>
        )}
      </div>

      {/* Info Popover */}
      {showInfo && description && (
        <div
          ref={popoverRef}
          className="absolute top-full left-0 mt-2 z-50 w-72 bg-white border border-border-subtle rounded-2xl shadow-xl p-4 animate-fade-in"
          style={{ boxShadow: '0 8px 32px rgba(15,23,42,0.12)' }}
        >
          <div className="flex items-start justify-between gap-2 mb-2">
            <span className="text-text-primary text-xs font-semibold uppercase tracking-wide">{title}</span>
            <button
              onClick={() => setShowInfo(false)}
              className="text-text-muted hover:text-text-primary transition-colors shrink-0"
            >
              <X size={13} />
            </button>
          </div>
          <p className="text-text-secondary text-xs leading-relaxed">{description}</p>
          <div className="mt-3 pt-3 border-t border-border-subtle flex items-center gap-2">
            <span
              className="w-2 h-2 rounded-full shrink-0"
              style={{ backgroundColor: accentColor }}
            />
            <span className="text-text-muted text-[10px]">Current value: <strong className="text-text-primary">{formatValue(value, format)}</strong></span>
          </div>
        </div>
      )}
    </div>
  )
}
