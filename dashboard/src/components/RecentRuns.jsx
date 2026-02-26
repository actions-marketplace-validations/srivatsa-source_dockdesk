import { Clock, GitBranch, FileText, CheckCircle, XCircle, MinusCircle, Wrench } from 'lucide-react'

export default function RecentRuns({ runs }) {
  if (!runs || runs.length === 0) {
    return (
      <div className="bg-surface-600 border border-white/5 rounded-xl p-6">
        <h3 className="text-sm font-semibold text-white mb-4">Recent Runs</h3>
        <p className="text-muted text-xs">No runs recorded yet.</p>
      </div>
    )
  }

  const formatTime = (timestamp) => {
    if (!timestamp) return ''
    const date = new Date(timestamp)
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  return (
    <div className="bg-surface-600 border border-white/5 rounded-xl p-6">
      <h3 className="text-sm font-semibold text-white mb-4">Recent Runs</h3>
      <div className="space-y-2.5">
        {runs.slice(0, 8).map((run, i) => (
          <div
            key={run.run_id || i}
            className="bg-surface-700 rounded-lg p-3.5 hover:bg-surface-500 transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2.5">
                <span className="text-xs text-muted font-mono">
                  #{(run.run_id || '').slice(-8)}
                </span>
                {run.git_branch && (
                  <span className="inline-flex items-center space-x-1 text-xs text-info bg-info-muted px-2 py-0.5 rounded-full">
                    <GitBranch size={10} />
                    <span>{run.git_branch}</span>
                  </span>
                )}
              </div>
              <span className="inline-flex items-center space-x-1 text-xs text-muted">
                <Clock size={10} />
                <span>{formatTime(run.timestamp)}</span>
              </span>
            </div>

            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center space-x-3">
                <span className="inline-flex items-center space-x-1 text-success">
                  <CheckCircle size={12} />
                  <span>{run.pass_count ?? 0}</span>
                </span>
                <span className="inline-flex items-center space-x-1 text-danger">
                  <XCircle size={12} />
                  <span>{run.fail_count ?? 0}</span>
                </span>
                {(run.skip_count ?? 0) > 0 && (
                  <span className="inline-flex items-center space-x-1 text-muted">
                    <MinusCircle size={12} />
                    <span>{run.skip_count}</span>
                  </span>
                )}
                {(run.fixes_applied ?? 0) > 0 && (
                  <span className="inline-flex items-center space-x-1 text-warning">
                    <Wrench size={12} />
                    <span>{run.fixes_applied}</span>
                  </span>
                )}
              </div>

              <div className="flex items-center space-x-3 text-muted">
                <span className="inline-flex items-center space-x-1">
                  <FileText size={10} />
                  <span>{run.files_audited ?? 0}</span>
                </span>
                <span>{(run.duration_seconds ?? 0).toFixed(1)}s</span>
                <span className="bg-surface-400 px-2 py-0.5 rounded text-[10px] font-mono">
                  {(run.model || '').replace('qwen2.5-coder:', 'qwen:')}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
