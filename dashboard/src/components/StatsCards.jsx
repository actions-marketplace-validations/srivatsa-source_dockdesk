import { FileText, CheckCircle, Wrench, Clock, TrendingUp, Cpu } from 'lucide-react'

export default function StatsCards({ stats, modelsUsed, files = [] }) {
  if (!stats) return null

  // Calculate pass rate from latest_run_files or timeline data
  const totalFiles = stats.total_files_audited ?? 0
  const totalFixes = stats.total_fixes_applied ?? 0
  const modelCount = modelsUsed?.length || Object.keys(stats.model_usage || {}).length || 0

  // Compute pass/fail ratio from latest run status data when available.
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
      label: 'Total Audits',
      value: stats.total_audits ?? 0,
      icon: CheckCircle,
      color: 'text-info',
      bg: 'bg-info-muted',
      sub: 'runs completed',
    },
    {
      label: 'Files Analyzed',
      value: (stats.total_files_audited ?? 0).toLocaleString(),
      icon: FileText,
      color: 'text-success',
      bg: 'bg-success-muted',
      sub: 'across all audits',
    },
    {
      label: 'Pass Rate',
      value: `${passRate}%`,
      icon: TrendingUp,
      color: passRate >= 70 ? 'text-success' : passRate >= 40 ? 'text-warning' : 'text-danger',
      bg: passRate >= 70 ? 'bg-success-muted' : passRate >= 40 ? 'bg-warning-muted' : 'bg-danger-muted',
      sub: passFailTotal > 0
        ? `${passCount} pass / ${failCount} fail`
        : `${riskTotals.LOW || 0} low risk of ${totalRisks}`,
    },
    {
      label: 'Models Active',
      value: modelCount,
      icon: Cpu,
      color: 'text-info',
      bg: 'bg-info-muted',
      sub: modelCount > 1 ? 'multi-model pipeline' : 'single model',
    },
    {
      label: 'Fixes Applied',
      value: stats.total_fixes_applied ?? 0,
      icon: Wrench,
      color: 'text-warning',
      bg: 'bg-warning-muted',
      sub: 'auto-corrections',
    },
    {
      label: 'Avg Duration',
      value: `${(stats.average_duration_seconds ?? 0).toFixed(1)}s`,
      icon: Clock,
      color: 'text-accent',
      bg: 'bg-accent-muted',
      sub: 'per audit run',
    },
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
      {cards.map((card) => {
        const Icon = card.icon
        return (
          <div
            key={card.label}
            className="bg-surface-600 border border-white/5 rounded-xl p-5 card-hover cursor-default"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs text-muted font-medium uppercase tracking-wider">{card.label}</p>
                <p className="text-2xl font-bold text-white mt-1.5">{card.value}</p>
              </div>
              <div className={`w-10 h-10 rounded-xl ${card.bg} flex items-center justify-center`}>
                <Icon size={20} className={card.color} />
              </div>
            </div>
            <p className="mt-3 text-xs text-muted">{card.sub}</p>
          </div>
        )
      })}
    </div>
  )
}
