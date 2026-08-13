import { motion } from 'framer-motion'

export default function RiskChart({ riskTotals = {} }) {
  const high = riskTotals.HIGH || 0
  const medium = riskTotals.MEDIUM || 0
  const low = riskTotals.LOW || 0
  const total = high + medium + low || 1

  const segments = [
    { label: 'HIGH', count: high, pct: Math.round((high / total) * 100), color: 'bg-pink', textColor: 'risk-high', glow: 'glow-pink' },
    { label: 'MEDIUM', count: medium, pct: Math.round((medium / total) * 100), color: 'bg-warning', textColor: 'risk-medium', glow: '' },
    { label: 'LOW', count: low, pct: Math.round((low / total) * 100), color: 'bg-success', textColor: 'risk-low', glow: '' },
  ]

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card rounded-xl p-5">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted mb-4">Risk Distribution</h3>

      {/* Horizontal stacked bar */}
      <div className="flex h-4 rounded-full overflow-hidden bg-surface-600 mb-5">
        {segments.map(s => s.count > 0 && (
          <motion.div key={s.label} initial={{ width: 0 }} animate={{ width: `${s.pct}%` }}
            transition={{ duration: 0.8, ease: 'easeOut' }}
            className={`${s.color} h-full`} title={`${s.label}: ${s.count}`}
          />
        ))}
      </div>

      {/* Legend */}
      <div className="flex justify-between">
        {segments.map(s => (
          <div key={s.label} className="text-center">
            <p className={`text-2xl font-bold ${s.textColor}`}>{s.count}</p>
            <p className="text-[10px] text-muted uppercase tracking-wider mt-0.5">{s.label}</p>
            <p className="text-xs text-muted">{s.pct}%</p>
          </div>
        ))}
      </div>
    </motion.div>
  )
}
