import { motion } from 'framer-motion'
import { FileText, CheckCircle, Wrench, Clock, TrendingUp, Cpu } from 'lucide-react'

const counter = {
  hidden: { opacity: 0, y: 20 },
  visible: (i) => ({ opacity: 1, y: 0, transition: { delay: i * 0.08, duration: 0.4, ease: 'easeOut' } }),
}

export default function StatsCards({ stats, modelsUsed, files = [] }) {
  if (!stats) return null

  const totalFiles = stats.total_files_audited ?? 0
  const modelCount = modelsUsed?.length || Object.keys(stats.model_usage || {}).length || 0

  const passCount = files.filter((f) => f.status === 'PASS').length
  const failCount = files.filter((f) => f.status === 'FAIL').length
  const passFailTotal = passCount + failCount
  const riskTotals = stats.risk_totals || {}
  const totalRisks = (riskTotals.HIGH || 0) + (riskTotals.MEDIUM || 0) + (riskTotals.LOW || 0)
  const passRate = passFailTotal > 0
    ? Math.round((passCount / passFailTotal) * 100)
    : (totalRisks > 0 ? Math.round(((riskTotals.LOW || 0) / totalRisks) * 100) : 0)

  const cards = [
    {
      label: 'Total Audits', value: stats.total_audits ?? 0, icon: CheckCircle,
      gradient: 'from-accent/20 to-accent/5', iconColor: 'text-accent-light', glowClass: '',
      sub: 'runs completed',
    },
    {
      label: 'Files Analyzed', value: (stats.total_files_audited ?? 0).toLocaleString(), icon: FileText,
      gradient: 'from-success/15 to-success/5', iconColor: 'text-success', glowClass: '',
      sub: 'across all audits',
    },
    {
      label: 'Pass Rate', value: `${passRate}%`, icon: TrendingUp,
      gradient: passRate >= 70 ? 'from-success/15 to-success/5' : passRate >= 40 ? 'from-warning/15 to-warning/5' : 'from-danger/15 to-danger/5',
      iconColor: passRate >= 70 ? 'text-success' : passRate >= 40 ? 'text-warning' : 'text-danger',
      glowClass: passRate < 40 ? 'glow-pink' : '',
      sub: passFailTotal > 0 ? `${passCount} pass / ${failCount} fail` : `${riskTotals.LOW || 0} low of ${totalRisks}`,
    },
    {
      label: 'Models Active', value: modelCount, icon: Cpu,
      gradient: 'from-accent/20 to-accent/5', iconColor: 'text-accent-light', glowClass: '',
      sub: modelCount > 1 ? 'multi-model pipeline' : 'single model',
    },
    {
      label: 'Fixes Applied', value: stats.total_fixes_applied ?? 0, icon: Wrench,
      gradient: 'from-warning/15 to-warning/5', iconColor: 'text-warning', glowClass: '',
      sub: 'auto-corrections',
    },
    {
      label: 'Avg Duration', value: `${(stats.average_duration_seconds ?? 0).toFixed(1)}s`, icon: Clock,
      gradient: 'from-pink/15 to-pink/5', iconColor: 'text-pink-light', glowClass: '',
      sub: 'per audit run',
    },
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
      {cards.map((card, i) => {
        const Icon = card.icon
        return (
          <motion.div
            key={card.label}
            custom={i}
            initial="hidden"
            animate="visible"
            variants={counter}
            className={`glass-card glass-card-hover rounded-xl p-5 cursor-default ${card.glowClass}`}
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-[10px] text-muted font-semibold uppercase tracking-wider">{card.label}</p>
                <p className="text-2xl font-bold text-white mt-1.5">{card.value}</p>
              </div>
              <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${card.gradient} flex items-center justify-center`}>
                <Icon size={20} className={card.iconColor} />
              </div>
            </div>
            <p className="mt-3 text-[11px] text-muted">{card.sub}</p>
          </motion.div>
        )
      })}
    </div>
  )
}
