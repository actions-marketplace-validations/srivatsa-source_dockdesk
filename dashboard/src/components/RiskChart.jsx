import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts'

export default function RiskChart({ riskTotals }) {
  const data = [
    { name: 'HIGH', value: riskTotals.HIGH, color: '#ef4444' },
    { name: 'MEDIUM', value: riskTotals.MEDIUM, color: '#eab308' },
    { name: 'LOW', value: riskTotals.LOW, color: '#22c55e' },
  ]

  const total = data.reduce((sum, item) => sum + item.value, 0)

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Risk Distribution</h3>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={80}
              paddingAngle={5}
              dataKey="value"
              label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip 
              formatter={(value, name) => [`${value} (${((value/total)*100).toFixed(1)}%)`, name]}
            />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-4 text-center">
        <div>
          <div className="text-2xl font-bold text-red-500">{riskTotals.HIGH}</div>
          <div className="text-xs text-gray-500">High Risk</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-yellow-500">{riskTotals.MEDIUM}</div>
          <div className="text-xs text-gray-500">Medium Risk</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-green-500">{riskTotals.LOW}</div>
          <div className="text-xs text-gray-500">Low Risk</div>
        </div>
      </div>
    </div>
  )
}
