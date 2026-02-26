import { Cpu } from 'lucide-react'

export default function ModelUsage({ modelUsage }) {
  if (!modelUsage || Object.keys(modelUsage).length === 0) {
    return (
      <div className="bg-surface-600 border border-white/5 rounded-xl p-6">
        <h3 className="text-sm font-semibold text-white mb-4">Model Usage</h3>
        <p className="text-muted text-xs">No model usage data yet.</p>
      </div>
    )
  }

  const entries = Object.entries(modelUsage).sort((a, b) => b[1] - a[1])
  const maxCount = Math.max(...entries.map(([, c]) => c), 1)

  return (
    <div className="bg-surface-600 border border-white/5 rounded-xl p-6">
      <div className="flex items-center space-x-2 mb-5">
        <Cpu size={16} className="text-info" />
        <h3 className="text-sm font-semibold text-white">Model Usage</h3>
      </div>
      <div className="space-y-3">
        {entries.map(([name, count]) => {
          const pct = Math.round((count / maxCount) * 100)
          return (
            <div key={name}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-muted font-mono truncate max-w-[180px]" title={name}>
                  {name}
                </span>
                <span className="text-xs font-semibold text-white ml-2">{count}</span>
              </div>
              <div className="h-2 bg-surface-400 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-info to-accent rounded-full transition-all duration-500"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
