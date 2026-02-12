import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

export default function AuditTimeline({ timeline }) {
  if (!timeline || timeline.length === 0) {
    return (
      <div className="bg-mono-card border border-mono-border p-6 retro-card">
        <h3 className="text-sm font-bold text-white mb-4 tracking-widest">AUDIT TIMELINE</h3>
        <p className="text-mono-dim text-xs">No timeline data. Run more audits to see trends.</p>
      </div>
    )
  }

  return (
    <div className="bg-mono-card border border-mono-border p-6 retro-card">
      <h3 className="text-sm font-bold text-white mb-4 tracking-widest">AUDIT TIMELINE</h3>
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={timeline}>
            <CartesianGrid strokeDasharray="3 3" stroke="#222" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: '#666', fontFamily: 'JetBrains Mono' }}
              tickFormatter={(value) => value.slice(5)}
              stroke="#333"
            />
            <YAxis tick={{ fontSize: 10, fill: '#666', fontFamily: 'JetBrains Mono' }} stroke="#333" />
            <Tooltip
              contentStyle={{ backgroundColor: '#0a0a0a', border: '1px solid #333', color: '#d4d4d4', fontFamily: 'JetBrains Mono, monospace', fontSize: '11px' }}
              labelFormatter={(value) => `Date: ${value}`}
            />
            <Legend wrapperStyle={{ color: '#666', fontFamily: 'JetBrains Mono', fontSize: '11px' }} />
            <Line type="monotone" dataKey="pass" stroke="#fff" strokeWidth={2} name="Pass" dot={{ fill: '#fff', r: 2 }} />
            <Line type="monotone" dataKey="fail" stroke="#888" strokeWidth={2} strokeDasharray="5 3" name="Fail" dot={{ fill: '#888', r: 2 }} />
            <Line type="monotone" dataKey="fixes" stroke="#444" strokeWidth={1} strokeDasharray="2 2" name="Fixes" dot={{ fill: '#444', r: 2 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
