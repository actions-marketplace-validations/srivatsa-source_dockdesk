import { motion } from 'framer-motion'
import { Activity } from 'lucide-react'

export default function AuditTimeline({ timeline = [] }) {
  if (!timeline || timeline.length === 0) {
    return (
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass-card rounded-xl p-5">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted mb-3">Audit Timeline</h3>
        <p className="text-muted text-sm">No timeline data yet.</p>
      </motion.div>
    )
  }

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card rounded-xl p-5">
      <div className="flex items-center space-x-2 mb-4">
        <Activity size={16} className="text-accent-light" />
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Audit Timeline</h3>
      </div>
      <div className="space-y-3">
        {timeline.slice(-10).reverse().map((entry, i) => {
          const date = String(entry.timestamp || entry.date || '').slice(0, 16).replace('T', ' ')
          const risk = entry.risk_distribution || {}
          const high = risk.HIGH || 0
          return (
            <motion.div key={i} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.04 }}
              className="flex items-center space-x-3 py-2 border-b border-accent/5 last:border-0">
              <div className={`w-2 h-2 rounded-full flex-shrink-0 ${high > 0 ? 'bg-pink glow-pink' : 'bg-success'}`} />
              <span className="text-xs text-muted font-mono w-32 flex-shrink-0">{date}</span>
              <span className="text-xs text-white">{entry.files_audited || 0} files</span>
              <span className="text-xs text-success">✔{entry.pass_count || 0}</span>
              <span className="text-xs text-pink">✘{entry.fail_count || 0}</span>
              {high > 0 && <span className="text-[10px] risk-high font-bold">▲{high} HIGH</span>}
            </motion.div>
          )
        })}
      </div>
    </motion.div>
  )
}
