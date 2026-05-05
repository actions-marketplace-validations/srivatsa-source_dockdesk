import { motion } from 'framer-motion'
import { Clock } from 'lucide-react'

export default function RecentRuns({ runs = [] }) {
  if (!runs || runs.length === 0) {
    return (
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass-card rounded-xl p-5">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted mb-3">Recent Runs</h3>
        <p className="text-muted text-sm">No recent runs.</p>
      </motion.div>
    )
  }

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-accent/10 flex items-center space-x-2">
        <Clock size={16} className="text-accent-light" />
        <h3 className="text-sm font-semibold text-white">Recent Runs ({runs.length})</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-wider text-muted">
              <th className="px-5 py-3">Date</th>
              <th className="px-3 py-3 text-center">Files</th>
              <th className="px-3 py-3 text-center">Pass</th>
              <th className="px-3 py-3 text-center">Fail</th>
              <th className="px-3 py-3 text-center">HIGH</th>
              <th className="px-3 py-3">Model</th>
              <th className="px-3 py-3 text-center">Duration</th>
            </tr>
          </thead>
          <tbody>
            {runs.slice(0, 20).map((run, i) => {
              const date = String(run.timestamp || '').slice(0, 16).replace('T', ' ')
              const risk = run.risk_distribution || {}
              return (
                <motion.tr key={i} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.03 }}
                  className="border-t border-accent/5 hover:bg-accent/5 transition">
                  <td className="px-5 py-2.5 text-muted font-mono text-xs">{date}</td>
                  <td className="px-3 py-2.5 text-center text-white">{run.files_audited || 0}</td>
                  <td className="px-3 py-2.5 text-center text-success">{run.pass_count || 0}</td>
                  <td className="px-3 py-2.5 text-center text-pink">{run.fail_count || 0}</td>
                  <td className="px-3 py-2.5 text-center">
                    {(risk.HIGH || 0) > 0 ? <span className="risk-high font-bold">{risk.HIGH}</span> : <span className="text-muted">0</span>}
                  </td>
                  <td className="px-3 py-2.5 text-xs text-muted font-mono truncate max-w-[120px]">{run.model || '-'}</td>
                  <td className="px-3 py-2.5 text-center text-xs text-muted">{run.duration_seconds ? `${run.duration_seconds.toFixed(1)}s` : '-'}</td>
                </motion.tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </motion.div>
  )
}
