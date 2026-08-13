import { motion } from 'framer-motion'
import { Shield, ShieldAlert, ShieldCheck } from 'lucide-react'

export default function PushSafety({ files = [] }) {
  const safe = files.filter(f => f.safe_to_push).length
  const unsafe = files.filter(f => f.safe_to_push === false).length
  const total = files.length || 1
  const safePct = Math.round((safe / total) * 100)

  const isSafe = unsafe === 0
  const StatusIcon = isSafe ? ShieldCheck : ShieldAlert

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
      className={`glass-card rounded-xl p-5 ${!isSafe ? 'border-pink/20' : 'border-success/20'}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Push Safety</h3>
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${isSafe ? 'bg-success/15 glow-cyan' : 'bg-pink/15 glow-pink'}`}>
          <StatusIcon size={20} className={isSafe ? 'text-success' : 'text-pink'} />
        </div>
      </div>

      <div className="flex items-end space-x-3 mb-4">
        <span className={`text-4xl font-bold ${isSafe ? 'text-success risk-low' : 'text-pink risk-high'}`}>{safePct}%</span>
        <span className="text-muted text-sm pb-1">safe to push</span>
      </div>

      {/* Progress bar */}
      <div className="h-2 rounded-full bg-surface-600 overflow-hidden mb-3">
        <motion.div initial={{ width: 0 }} animate={{ width: `${safePct}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          className={`h-full rounded-full ${isSafe ? 'bg-success' : 'bg-gradient-to-r from-pink to-warning'}`}
        />
      </div>

      <div className="flex justify-between text-xs">
        <span className="text-success flex items-center gap-1"><ShieldCheck size={14} /> {safe} safe</span>
        <span className="text-pink flex items-center gap-1"><ShieldAlert size={14} /> {unsafe} unsafe</span>
      </div>
    </motion.div>
  )
}
