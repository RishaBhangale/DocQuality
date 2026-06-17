import type { TimeRange } from '../../types'

interface TimeRangePickerProps {
  value: TimeRange
  onChange: (range: TimeRange) => void
}

const OPTIONS: { label: string; value: TimeRange }[] = [
  { label: '7d', value: '7d' },
  { label: '30d', value: '30d' },
  { label: '90d', value: '90d' },
  { label: 'All', value: 'all' },
]

function getDateRange(range: TimeRange): { from_date: string; to_date: string } {
  const now = new Date()
  const to_date = now.toISOString().slice(0, 10)
  if (range === 'all') return { from_date: '', to_date: '' }
  const days = range === '7d' ? 7 : range === '30d' ? 30 : 90
  const from = new Date(now.getTime() - days * 86_400_000)
  return { from_date: from.toISOString().slice(0, 10), to_date }
}

export { getDateRange }

export function TimeRangePicker({ value, onChange }: TimeRangePickerProps) {
  return (
    <div className="flex items-center bg-surface rounded-xl p-0.5 border border-border-subtle">
      {OPTIONS.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`
            px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200
            ${value === opt.value
              ? 'bg-accent-cyan/15 text-accent-cyan shadow-sm'
              : 'text-text-muted hover:text-text-secondary'
            }
          `}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}
