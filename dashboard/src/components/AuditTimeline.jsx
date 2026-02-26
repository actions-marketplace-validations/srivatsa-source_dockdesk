import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload) return null
  return (
    <div className="bg-surface-800 border border-white/10 rounded-lg px-3 py-2 shadow-lg text-xs">
      <p className="text-muted mb-1">{label}</p>
      {payload.map((entry, i) => (
        <p key={i} style={{ color: entry.color }} className="font-medium">
          {entry.name}: {entry.value}
        </p>
      ))}
    </div>
  )
}

export default function AuditTimeline({ timeline }) {
  if (!timeline || timeline.length === 0) {
    return (
      <div className="bg-surface-600 border border-white/5 rounded-xl p-6">
        <h3 className="text-sm font-semibold text-white mb-4">Audit Timeline</h3>
        <p className="text-muted text-xs">No timeline data yet. Run more audits to see trends.</p>
      </div>
    )
  }

  return (
    <div className="bg-surface-600 border border-white/5 rounded-xl p-6">
      <h3 className="text-sm font-semibold text-white mb-4">Audit Timeline</h3>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={timeline}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: '#64748b', fontFamily: 'Inter' }}
              tickFormatter={(value) => value.slice(5)}
              stroke="rgba(255,255,255,0.08)"
              axisLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: '#64748b', fontFamily: 'Inter' }}
              stroke="rgba(255,255,255,0.08)"
              axisLine={false}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ fontSize: '12px', fontFamily: 'Inter' }}
              iconType="circle"
              iconSize={8}
            />
            <Line
              type="monotone" dataKey="pass" stroke="#10b981" strokeWidth={2}
              name="Pass" dot={{ fill: '#10b981', r: 3, strokeWidth: 0 }}
              activeDot={{ r: 5, strokeWidth: 0 }}
            />
            <Line
              type="monotone" dataKey="fail" stroke="#ef4444" strokeWidth={2}
              name="Fail" dot={{ fill: '#ef4444', r: 3, strokeWidth: 0 }}
              activeDot={{ r: 5, strokeWidth: 0 }}
            />
            <Line
              type="monotone" dataKey="fixes" stroke="#f59e0b" strokeWidth={1.5}
              strokeDasharray="4 3" name="Fixes" dot={{ fill: '#f59e0b', r: 2, strokeWidth: 0 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
