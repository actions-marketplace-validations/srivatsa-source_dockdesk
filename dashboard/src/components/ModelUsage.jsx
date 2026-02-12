import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

export default function ModelUsage({ modelUsage }) {
  if (!modelUsage || Object.keys(modelUsage).length === 0) {
    return (
      <div className="bg-mono-card border border-mono-border p-6 retro-card">
        <h3 className="text-sm font-bold text-white mb-4 tracking-widest">MODEL USAGE</h3>
        <p className="text-mono-dim text-xs">No model usage data yet.</p>
      </div>
    )
  }

  const data = Object.entries(modelUsage).map(([name, count]) => ({
    name: name.length > 18 ? name.slice(0, 16) + '..' : name,
    count,
    fullName: name
  }))

  return (
    <div className="bg-mono-card border border-mono-border p-6 retro-card">
      <h3 className="text-sm font-bold text-white mb-4 tracking-widest">MODEL USAGE</h3>
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke="#222" />
            <XAxis type="number" tick={{ fontSize: 10, fill: '#666', fontFamily: 'JetBrains Mono' }} stroke="#333" />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fontSize: 10, fill: '#666', fontFamily: 'JetBrains Mono' }}
              width={90}
              stroke="#333"
            />
            <Tooltip
              contentStyle={{ backgroundColor: '#0a0a0a', border: '1px solid #333', color: '#d4d4d4', fontFamily: 'JetBrains Mono, monospace', fontSize: '11px' }}
              formatter={(value) => [`${value} runs`, 'Usage']}
              labelFormatter={(_, payload) => payload[0]?.payload?.fullName || ''}
            />
            <Bar dataKey="count" fill="#fff" radius={[0, 2, 2, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
