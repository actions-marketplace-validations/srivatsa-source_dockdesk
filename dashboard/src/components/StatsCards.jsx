export default function StatsCards({ stats }) {
  if (!stats) return null
  
  const cards = [
    {
      label: 'AUDITS',
      value: stats.total_audits ?? 0,
      symbol: '[#]',
      sub: 'total runs completed'
    },
    {
      label: 'FILES',
      value: (stats.total_files_audited ?? 0).toLocaleString(),
      symbol: '[>]',
      sub: 'files analyzed'
    },
    {
      label: 'FIXES',
      value: stats.total_fixes_applied ?? 0,
      symbol: '[~]',
      sub: 'auto-applied'
    },
    {
      label: 'AVG TIME',
      value: `${(stats.average_duration_seconds ?? 0).toFixed(1)}s`,
      symbol: '[*]',
      sub: 'per audit run'
    },
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card) => (
        <div key={card.label} className="bg-mono-card border border-mono-border p-5 retro-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-mono-dim tracking-widest">{card.label}</p>
              <p className="text-2xl font-bold text-white mt-1">{card.value}</p>
            </div>
            <span className="text-mono-dim text-lg font-mono">{card.symbol}</span>
          </div>
          <p className="mt-2 text-xs text-mono-dim">{card.sub}</p>
        </div>
      ))}
    </div>
  )
}
