import { Tooltip as RechartsTooltip } from 'recharts'
import type { TooltipProps } from 'recharts'

type ValueType = string | number | (string | number)[]
type NameType = string | number

export function CustomTooltip({
  active,
  payload,
  label,
}: TooltipProps<ValueType, NameType>) {
  if (!active || !payload?.length) return null

  return (
    <div className="bg-white border border-border-subtle rounded-xl px-4 py-3 shadow-lg">
      {label && (
        <p className="text-text-muted text-xs mb-2 font-medium">{label}</p>
      )}
      {payload.map((entry, i) => (
        <div key={i} className="flex items-center gap-2 text-xs py-0.5">
          <span
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-text-secondary">{entry.name}:</span>
          <span className="text-text-primary font-semibold">
            {typeof entry.value === 'number'
              ? entry.value.toLocaleString(undefined, { maximumFractionDigits: 2 })
              : entry.value}
          </span>
        </div>
      ))}
    </div>
  )
}

export { RechartsTooltip }
