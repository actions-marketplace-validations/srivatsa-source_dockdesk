import { FileText, CheckCircle, Wrench, Clock } from 'lucide-react'

export default function StatsCards({ stats }) {
  if (!stats) return null

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
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
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
