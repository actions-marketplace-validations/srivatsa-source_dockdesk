import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

export default function AuditTimeline({ timeline }) {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Audit Timeline</h3>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={timeline}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis 
              dataKey="date" 
              tick={{ fontSize: 12 }}
              tickFormatter={(value) => value.slice(5)} // Show MM-DD
            />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip 
              contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e7eb' }}
              labelFormatter={(value) => `Date: ${value}`}
            />
            <Legend />
            <Line 
              type="monotone" 
              dataKey="pass" 
              stroke="#22c55e" 
              strokeWidth={2}
              name="Pass"
              dot={{ fill: '#22c55e' }}
            />
            <Line 
              type="monotone" 
              dataKey="fail" 
              stroke="#ef4444" 
              strokeWidth={2}
              name="Fail"
              dot={{ fill: '#ef4444' }}
            />
            <Line 
              type="monotone" 
              dataKey="fixes" 
              stroke="#8b5cf6" 
              strokeWidth={2}
              name="Fixes"
              dot={{ fill: '#8b5cf6' }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
