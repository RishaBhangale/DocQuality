import { Loader2, AlertTriangle, Inbox } from 'lucide-react'

export function LoadingState({ message = 'Loading data…' }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <Loader2 size={28} className="text-accent-cyan animate-spin" />
      <span className="text-text-muted text-sm">{message}</span>
    </div>
  )
}

export function ErrorState({
  message = 'Failed to load data',
  onRetry,
}: {
  message?: string
  onRetry?: () => void
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <AlertTriangle size={28} className="text-accent-amber" />
      <span className="text-text-secondary text-sm">{message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-2 px-4 py-1.5 text-xs font-medium bg-accent-cyan/10 text-accent-cyan rounded-lg hover:bg-accent-cyan/20 transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  )
}

export function EmptyState({ message = 'No data available' }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <Inbox size={28} className="text-text-muted" />
      <span className="text-text-muted text-sm">{message}</span>
    </div>
  )
}
