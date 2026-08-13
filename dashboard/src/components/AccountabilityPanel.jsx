import { motion } from 'framer-motion'
import { Users, AlertTriangle, Award, TrendingDown, Shield } from 'lucide-react'

export default function AccountabilityPanel({ accountability = {}, files = [] }) {
  const developers = accountability?.developers || {}
  const topOffenders = accountability?.top_offenders || []
  const cleanStreaks = accountability?.clean_streaks || []
  const teams = accountability?.teams || {}

  const sortedDevs = Object.values(developers).sort((a, b) => (b.drift_score || 0) - (a.drift_score || 0))

  if (sortedDevs.length === 0) {
    return (
      <div className="glass-card rounded-xl p-8 text-center">
        <Users size={32} className="text-accent-light mx-auto mb-3 opacity-50" />
        <h3 className="text-white font-medium mb-1">No Accountability Data</h3>
        <p className="text-muted text-sm">Run an audit on a git repository to track per-developer drift.</p>
      </div>
    )
  }

  const getDriftColor = (score) => {
    if (score >= 5) return 'text-pink risk-high'
    if (score >= 2) return 'text-warning risk-medium'
    return 'text-success risk-low'
  }

  const getDriftBar = (score, max = 10) => {
    const pct = Math.min((score / max) * 100, 100)
    const color = score >= 5 ? 'bg-pink' : score >= 2 ? 'bg-warning' : 'bg-success'
    return (
      <div className="w-full h-1.5 rounded-full bg-white/5 overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          className={`h-full rounded-full ${color}`}
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card rounded-xl p-5">
          <div className="flex items-center space-x-3 mb-3">
            <div className="w-8 h-8 rounded-lg bg-pink/15 flex items-center justify-center">
              <AlertTriangle size={16} className="text-pink" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-muted">Top Offenders</span>
          </div>
          {topOffenders.length > 0 ? topOffenders.slice(0, 3).map((d, i) => (
            <div key={i} className="flex justify-between items-center py-1.5 border-b border-white/5 last:border-0">
              <span className="text-sm text-white">{d.name}</span>
              <span className={`text-sm font-mono font-bold ${getDriftColor(d.drift_score)}`}>{d.drift_score?.toFixed(1)}</span>
            </div>
          )) : <p className="text-muted text-xs">No drift detected </p>}
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="glass-card rounded-xl p-5">
          <div className="flex items-center space-x-3 mb-3">
            <div className="w-8 h-8 rounded-lg bg-success/15 flex items-center justify-center">
              <Award size={16} className="text-success" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-muted">Clean Streaks</span>
          </div>
          {cleanStreaks.length > 0 ? cleanStreaks.slice(0, 3).map((d, i) => (
            <div key={i} className="flex justify-between items-center py-1.5 border-b border-white/5 last:border-0">
              <span className="text-sm text-white">{d.name}</span>
              <span className="text-sm text-success font-mono">{d.files_passed}/{d.files_authored}</span>
            </div>
          )) : <p className="text-muted text-xs">Run more audits to track streaks</p>}
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="glass-card rounded-xl p-5">
          <div className="flex items-center space-x-3 mb-3">
            <div className="w-8 h-8 rounded-lg bg-accent/15 flex items-center justify-center">
              <Shield size={16} className="text-accent-light" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-muted">Teams</span>
          </div>
          {Object.entries(teams).slice(0, 4).map(([name, data]) => (
            <div key={name} className="flex justify-between items-center py-1.5 border-b border-white/5 last:border-0">
              <span className="text-sm text-white truncate">{name}</span>
              <span className={`text-sm font-mono ${getDriftColor(data.aggregate_drift || 0)}`}>
                {(data.aggregate_drift || 0).toFixed(1)}
              </span>
            </div>
          ))}
        </motion.div>
      </div>

      {/* Full developer table */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="glass-card rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-accent/10">
          <h3 className="text-sm font-semibold text-white">Developer Accountability ({sortedDevs.length})</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[10px] uppercase tracking-wider text-muted">
                <th className="px-5 py-3">Developer</th>
                <th className="px-3 py-3 text-center">Files</th>
                <th className="px-3 py-3 text-center">Pass</th>
                <th className="px-3 py-3 text-center">Fail</th>
                <th className="px-3 py-3 text-center">HIGH</th>
                <th className="px-3 py-3">Drift Score</th>
                <th className="px-3 py-3">Team</th>
              </tr>
            </thead>
            <tbody>
              {sortedDevs.map((dev, i) => (
                <motion.tr
                  key={dev.name}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.05 * i }}
                  className="border-t border-white/5 hover:bg-accent/5 transition"
                >
                  <td className="px-5 py-3 text-white font-medium">{dev.name}</td>
                  <td className="px-3 py-3 text-center text-muted">{dev.files_authored}</td>
                  <td className="px-3 py-3 text-center text-success">{dev.files_passed}</td>
                  <td className="px-3 py-3 text-center text-pink">{dev.files_failed}</td>
                  <td className="px-3 py-3 text-center">
                    {dev.high_risk_count > 0 ? <span className="risk-high font-bold">{dev.high_risk_count}</span> : <span className="text-muted">0</span>}
                  </td>
                  <td className="px-3 py-3 w-32">
                    <div className="flex items-center space-x-2">
                      <span className={`font-mono font-bold text-xs ${getDriftColor(dev.drift_score || 0)}`}>
                        {(dev.drift_score || 0).toFixed(1)}
                      </span>
                      {getDriftBar(dev.drift_score || 0)}
                    </div>
                  </td>
                  <td className="px-3 py-3 text-muted text-xs truncate max-w-[120px]">{dev.team || 'N/A'}</td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>
    </div>
  )
}
