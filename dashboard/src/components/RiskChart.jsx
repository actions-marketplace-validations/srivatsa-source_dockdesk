import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'

const RISK_COLORS = {
  HIGH: '#ef4444',
  MEDIUM: '#f59e0b',
  LOW: '#10b981',
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload || !payload.length) return null
  const d = payload[0]
  return (
    <div className="bg-surface-800 border border-white/10 rounded-lg px-3 py-2 shadow-lg text-xs">
      <p className="font-medium" style={{ color: d.payload.color }}>{d.name}</p>
      <p className="text-white">{d.value} issues ({d.payload.percent}%)</p>
    </div>
  )
}

export default function RiskChart({ riskTotals }) {
  if (!riskTotals) return null

  const total = (riskTotals.HIGH || 0) + (riskTotals.MEDIUM || 0) + (riskTotals.LOW || 0) || 1

  const data = [
    { name: 'High', value: riskTotals.HIGH || 0, color: RISK_COLORS.HIGH, percent: Math.round(((riskTotals.HIGH || 0) / total) * 100) },
    { name: 'Medium', value: riskTotals.MEDIUM || 0, color: RISK_COLORS.MEDIUM, percent: Math.round(((riskTotals.MEDIUM || 0) / total) * 100) },
    { name: 'Low', value: riskTotals.LOW || 0, color: RISK_COLORS.LOW, percent: Math.round(((riskTotals.LOW || 0) / total) * 100) },
  ]

  return (
    <div className="bg-surface-600 border border-white/5 rounded-xl p-6">
      <h3 className="text-sm font-semibold text-white mb-4">Risk Distribution</h3>
      <div className="flex items-center">
        <div className="w-44 h-44">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={48}
                outerRadius={68}
                paddingAngle={4}
                dataKey="value"
                stroke="none"
                animationBegin={0}
                animationDuration={800}
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="flex-1 space-y-3 ml-4">
          {data.map((item) => (
            <div key={item.name} className="flex items-center justify-between">
              <div className="flex items-center space-x-2.5">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                <span className="text-sm text-muted">{item.name}</span>
              </div>
              <div className="flex items-center space-x-3">
                <span className="text-sm font-semibold text-white">{item.value}</span>
                <span className="text-xs text-muted w-10 text-right">{item.percent}%</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
