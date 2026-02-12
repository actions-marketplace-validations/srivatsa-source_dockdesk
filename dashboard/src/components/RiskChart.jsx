import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'

export default function RiskChart({ riskTotals }) {
  if (!riskTotals) return null

  const data = [
    { name: 'HIGH', value: riskTotals.HIGH || 0, color: '#ffffff' },
    { name: 'MEDIUM', value: riskTotals.MEDIUM || 0, color: '#888888' },
    { name: 'LOW', value: riskTotals.LOW || 0, color: '#444444' },
  ]

  const total = data.reduce((sum, item) => sum + item.value, 0) || 1

  return (
    <div className="bg-mono-card border border-mono-border p-6 retro-card">
      <h3 className="text-sm font-bold text-white mb-4 tracking-widest">RISK DISTRIBUTION</h3>
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={45}
              outerRadius={65}
              paddingAngle={3}
              dataKey="value"
              stroke="#000"
              strokeWidth={2}
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{ backgroundColor: '#0a0a0a', border: '1px solid #333', color: '#d4d4d4', fontFamily: 'JetBrains Mono, monospace', fontSize: '12px' }}
              formatter={(value, name) => [`${value} (${((value/total)*100).toFixed(0)}%)`, name]}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-4 text-center font-mono">
        <div>
          <div className="text-2xl font-bold text-white">{riskTotals.HIGH || 0}</div>
          <div className="text-xs text-mono-dim">HIGH</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-mono-dim">{riskTotals.MEDIUM || 0}</div>
          <div className="text-xs text-mono-dim">MED</div>
        </div>
        <div>
          <div className="text-2xl font-bold" style={{color: '#444'}}>{riskTotals.LOW || 0}</div>
          <div className="text-xs text-mono-dim">LOW</div>
        </div>
      </div>
    </div>
  )
}
