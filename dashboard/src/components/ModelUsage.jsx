import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

export default function ModelUsage({ modelUsage }) {
  const data = Object.entries(modelUsage).map(([name, count]) => ({
    name: name.replace('qwen2.5-coder:', 'qwen:'),
    count,
    fullName: name
  }))

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Model Usage</h3>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" tick={{ fontSize: 12 }} />
            <YAxis 
              type="category" 
              dataKey="name" 
              tick={{ fontSize: 12 }}
              width={80}
            />
            <Tooltip 
              formatter={(value) => [`${value} runs`, 'Usage']}
              labelFormatter={(_, payload) => payload[0]?.payload?.fullName || ''}
            />
            <Bar 
              dataKey="count" 
              fill="#3b82f6" 
              radius={[0, 4, 4, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-4 text-sm text-gray-500">
        <p className="flex items-center">
          <span className="w-3 h-3 bg-blue-500 rounded-full mr-2"></span>
          Number of audit runs per model
        </p>
      </div>
    </div>
  )
}
