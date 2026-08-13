import { motion } from 'framer-motion'
import { Cpu, Brain, Code } from 'lucide-react'

export default function ModelUsage({ modelUsage, dualModel, modelsUsed, availableModels, latestFiles = [] }) {
  const hasData = (modelUsage && Object.keys(modelUsage).length > 0) || (availableModels && availableModels.length > 0)
  const hasDualModel = dualModel && (dualModel.code_model || dualModel.reasoning_model)

  if (!hasData && !hasDualModel) {
    return (
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass-card rounded-xl p-6">
        <h3 className="text-sm font-semibold text-white mb-4">Model Usage</h3>
        <p className="text-muted text-xs">No model usage data yet.</p>
      </motion.div>
    )
  }

  const entriesMap = { ...(modelUsage || {}) }
  if (availableModels) {
    availableModels.forEach((m) => {
      if (!(m in entriesMap)) {
        entriesMap[m] = 0
      }
    })
  }
  const entries = Object.entries(entriesMap).sort((a, b) => b[1] - a[1])
  const maxCount = Math.max(...entries.map(([, c]) => c), 1)

  // Compute diversity score
  const totalModels = Object.values(modelUsage || {}).length || 0
  const available = availableModels?.length || 0
  const diversityPct = available > 0 ? Math.round((totalModels / available) * 100) : 0
  const distinctFileModels = Array.from(new Set((latestFiles || []).map((f) => f.code_model).filter(Boolean)))
  const rotationActive = distinctFileModels.length > 1

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="glass-card glass-card-hover rounded-xl p-6"
    >
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center space-x-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-purple-500/20 to-pink-500/20 flex items-center justify-center">
            <Cpu size={14} className="text-purple-400" />
          </div>
          <h3 className="text-sm font-semibold text-white">Model Usage</h3>
        </div>
        {totalModels > 0 && (
          <span className="text-[10px] text-purple-300 bg-purple-500/10 border border-purple-500/20 px-2 py-0.5 rounded-full">
            {totalModels} model{totalModels > 1 ? 's' : ''} active
          </span>
        )}
      </div>

      {/* Dual-model architecture display */}
      {hasDualModel && (
        <div className="mb-5">
          <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold mb-2">Architecture</p>
          <div className="grid grid-cols-2 gap-3">
            <motion.div
              whileHover={{ scale: 1.02 }}
              className="glass-card rounded-lg p-3"
            >
              <div className="flex items-center space-x-2 mb-1">
                <Code size={14} className="text-cyan-400" />
                <span className="text-[10px] text-cyan-400 font-semibold uppercase">Code Model</span>
              </div>
              <p className="text-xs text-white font-mono">{dualModel.code_model || '-'}</p>
              <p className="text-[10px] text-slate-500 mt-1">Drift detection & analysis</p>
            </motion.div>
            <motion.div
              whileHover={{ scale: 1.02 }}
              className="glass-card rounded-lg p-3"
            >
              <div className="flex items-center space-x-2 mb-1">
                <Brain size={14} className="text-purple-400" />
                <span className="text-[10px] text-purple-400 font-semibold uppercase">Reasoning</span>
              </div>
              <p className="text-xs text-white font-mono">{dualModel.reasoning_model || '-'}</p>
              <p className="text-[10px] text-slate-500 mt-1">Risk assessment & judgement</p>
            </motion.div>
          </div>
        </div>
      )}

      {/* Model diversity score */}
      {available > 0 && (
        <div className="mb-5">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">Model Diversity</span>
            <span className="text-xs text-white font-semibold">{diversityPct}%</span>
          </div>
          <div className="h-2 bg-surface-400 rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${diversityPct}%` }}
              transition={{ duration: 0.8, ease: 'easeOut' }}
              className={`h-full rounded-full ${
                diversityPct >= 50
                  ? 'bg-gradient-to-r from-cyan-500 to-cyan-400'
                  : diversityPct >= 25
                  ? 'bg-gradient-to-r from-yellow-500 to-yellow-400'
                  : 'bg-gradient-to-r from-pink-500 to-pink-400'
              }`}
            />
          </div>
          <p className="text-[10px] text-slate-600 mt-1">
            {totalModels} of {available} available models used
          </p>
        </div>
      )}

      {/* Usage bars */}
      {entries.length > 0 && (
        <div>
          <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold mb-2">Run History</p>
          <div className="space-y-3">
            {entries.map(([name, count], idx) => {
              const pct = Math.round((count / maxCount) * 100)
              const isCode = name.includes('coder') || name.includes('codellama') || name.includes('starcoder')
              const isReasoning = name.includes('deepseek-r1') || name.includes('reasoning')
              const gradientClass = isReasoning
                ? 'from-purple-500 to-pink-500'
                : isCode
                ? 'from-cyan-500 to-blue-500'
                : 'from-purple-400 to-cyan-400'

              return (
                <motion.div
                  key={name}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.05 }}
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center space-x-1.5">
                      {isReasoning ? (
                        <Brain size={12} className="text-purple-400" />
                      ) : (
                        <Code size={12} className="text-cyan-400" />
                      )}
                      <span className="text-xs text-muted font-mono truncate max-w-[180px]" title={name}>
                        {name}
                      </span>
                    </div>
                    <span className="text-xs font-semibold text-white ml-2">{count}</span>
                  </div>
                  <div className="h-2 bg-surface-400 rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${pct}%` }}
                      transition={{ duration: 0.6, delay: idx * 0.05 }}
                      className={`h-full bg-gradient-to-r ${gradientClass} rounded-full`}
                    />
                  </div>
                </motion.div>
              )
            })}
          </div>
        </div>
      )}

      {/* Available models list */}
      {availableModels && availableModels.length > 0 && (
        <div className="mt-5 pt-4 border-t border-purple-500/10">
          <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold mb-2">Available Models</p>
          <div className="flex flex-wrap gap-1.5">
            {availableModels.map((m) => {
              const isUsed = modelsUsed?.includes(m)
              return (
                <span
                  key={m}
                  className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${
                    isUsed
                      ? 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/20'
                      : 'bg-white/5 text-slate-500 border border-white/5'
                  }`}
                >
                  {m}
                </span>
              )
            })}
          </div>
        </div>
      )}

      {/* Per-file assignment when rotation is active */}
      {rotationActive && latestFiles.length > 0 && (
        <div className="mt-5 pt-4 border-t border-purple-500/10">
          <div className="flex items-center justify-between mb-2">
            <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">Per-File Assignment</p>
            <span className="text-[10px] text-cyan-400 bg-cyan-500/10 border border-cyan-500/20 px-2 py-0.5 rounded-full">
              rotation active
            </span>
          </div>
          <div className="space-y-1.5 max-h-44 overflow-y-auto pr-1">
            {latestFiles.slice(0, 25).map((f, i) => (
              <motion.div
                key={`${f.file}-${f.code_model}`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.03 }}
                className="flex items-center justify-between text-[11px] glass-card rounded-md px-2 py-1.5"
              >
                <span className="text-slate-300 font-mono truncate pr-2" title={f.file}>{f.file}</span>
                <span className="text-cyan-400 font-mono whitespace-nowrap">{f.code_model || '-'}</span>
              </motion.div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  )
}
