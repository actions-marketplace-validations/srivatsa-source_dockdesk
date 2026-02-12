export default function RecentRuns({ runs }) {
  if (!runs || runs.length === 0) {
    return (
      <div className="bg-mono-card border border-mono-border p-6 retro-card">
        <h3 className="text-sm font-bold text-white mb-4 tracking-widest">RECENT RUNS</h3>
        <p className="text-mono-dim text-xs">No runs recorded yet.</p>
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
    <div className="bg-mono-card border border-mono-border p-6 retro-card">
      <h3 className="text-sm font-bold text-white mb-4 tracking-widest">RECENT RUNS</h3>
      <div className="space-y-2">
        {runs.slice(0, 8).map((run, i) => (
          <div
            key={run.run_id || i}
            className="border border-mono-border p-3 hover:border-white/30 transition font-mono"
          >
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center space-x-3">
                <span className="text-xs text-mono-dim">
                  #{(run.run_id || '').slice(-8)}
                </span>
                {run.git_branch && (
                  <span className="text-xs text-white border border-mono-border px-2 py-0.5">
                    {run.git_branch}
                  </span>
                )}
              </div>
              <span className="text-xs text-mono-dim">{formatTime(run.timestamp)}</span>
            </div>

            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center space-x-4">
                <span className="text-white">
                  PASS:{run.pass_count ?? 0}
                </span>
                <span className="text-mono-dim">
                  FAIL:{run.fail_count ?? 0}
                </span>
                {(run.fixes_applied ?? 0) > 0 && (
                  <span className="text-mono-dim">
                    FIX:{run.fixes_applied}
                  </span>
                )}
              </div>

              <div className="flex items-center space-x-3 text-mono-dim">
                <span>{run.files_audited ?? 0} files</span>
                <span>{(run.duration_seconds ?? 0).toFixed(1)}s</span>
                <span className="border border-mono-border px-2 py-0.5 text-xs">
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
