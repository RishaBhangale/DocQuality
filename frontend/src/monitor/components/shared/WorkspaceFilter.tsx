import type { Workspace } from '../../types'

interface WorkspaceFilterProps {
  value: Workspace
  onChange: (ws: Workspace) => void
}

const OPTIONS: { label: string; value: Workspace }[] = [
  { label: 'All', value: 'all' },
  { label: 'Banking', value: 'banking' },
  { label: 'Compliance', value: 'compliance' },
]

export function WorkspaceFilter({ value, onChange }: WorkspaceFilterProps) {
  return (
    <div className="flex items-center bg-surface rounded-xl p-0.5 border border-border-subtle">
      {OPTIONS.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`
            px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200
            ${value === opt.value
              ? 'bg-accent-purple/15 text-accent-purple shadow-sm'
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
