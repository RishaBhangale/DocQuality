import { Component } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

interface Props {
  children: React.ReactNode
  tabName?: string
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error(`[Observatory ErrorBoundary] Tab "${this.props.tabName}" crashed:`, error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[400px] gap-4 animate-fade-in">
          <div className="p-4 rounded-full bg-accent-amber/10">
            <AlertTriangle size={32} className="text-accent-amber" />
          </div>
          <div className="text-center max-w-md">
            <h3 className="text-text-primary font-semibold text-base mb-1">
              {this.props.tabName ? `${this.props.tabName} tab failed to render` : 'Something went wrong'}
            </h3>
            <p className="text-text-secondary text-sm mb-1">
              A render error occurred in this panel. The rest of the observatory is unaffected.
            </p>
            {this.state.error && (
              <p className="text-text-muted text-xs font-mono bg-slate-50 border border-border-subtle rounded-xl px-3 py-2 mt-2 text-left">
                {this.state.error.message}
              </p>
            )}
          </div>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="flex items-center gap-2 px-4 py-2 bg-accent-cyan text-white rounded-xl text-sm font-medium hover:opacity-90 transition-opacity"
          >
            <RefreshCw size={14} />
            Retry
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
