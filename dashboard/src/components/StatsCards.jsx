import { FileText, Zap, CheckCircle, Clock } from 'lucide-react'

export default function StatsCards({ stats }) {
  const cards = [
    {
      title: 'Total Audits',
      value: stats.total_audits,
      icon: FileText,
      color: 'blue',
      description: 'Audit runs completed'
    },
    {
      title: 'Files Audited',
      value: stats.total_files_audited.toLocaleString(),
      icon: CheckCircle,
      color: 'green',
      description: 'Total files analyzed'
    },
    {
      title: 'Fixes Applied',
      value: stats.total_fixes_applied,
      icon: Zap,
      color: 'purple',
      description: 'Auto-applied documentation fixes'
    },
    {
      title: 'Avg Duration',
      value: `${stats.average_duration_seconds}s`,
      icon: Clock,
      color: 'orange',
      description: 'Average audit time'
    },
  ]

  const colorClasses = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    purple: 'bg-purple-50 text-purple-600',
    orange: 'bg-orange-50 text-orange-600',
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {cards.map((card) => (
        <div key={card.title} className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center">
            <div className={`p-3 rounded-lg ${colorClasses[card.color]}`}>
              <card.icon className="h-6 w-6" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">{card.title}</p>
              <p className="text-2xl font-bold text-gray-900">{card.value}</p>
            </div>
          </div>
          <p className="mt-2 text-xs text-gray-400">{card.description}</p>
        </div>
      ))}
    </div>
  )
}
