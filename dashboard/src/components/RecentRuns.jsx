import { CheckCircle, XCircle, GitBranch, Clock, Zap } from 'lucide-react'

export default function RecentRuns({ runs }) {
  const formatTime = (timestamp) => {
    const date = new Date(timestamp)
    return date.toLocaleString('en-US', { 
      month: 'short', 
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Recent Audit Runs</h3>
      <div className="space-y-4">
        {runs.map((run) => (
          <div 
            key={run.run_id} 
            className="border border-gray-100 rounded-lg p-4 hover:bg-gray-50 transition"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2">
                <span className="text-sm font-mono text-gray-500">{run.run_id.slice(-10)}</span>
                {run.git_branch && (
                  <span className="flex items-center text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded">
                    <GitBranch className="h-3 w-3 mr-1" />
                    {run.git_branch}
                  </span>
                )}
              </div>
              <span className="text-xs text-gray-400">{formatTime(run.timestamp)}</span>
            </div>
            
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <span className="flex items-center text-sm text-green-600">
                  <CheckCircle className="h-4 w-4 mr-1" />
                  {run.pass_count}
                </span>
                <span className="flex items-center text-sm text-red-600">
                  <XCircle className="h-4 w-4 mr-1" />
                  {run.fail_count}
                </span>
                {run.fixes_applied > 0 && (
                  <span className="flex items-center text-sm text-purple-600">
                    <Zap className="h-4 w-4 mr-1" />
                    {run.fixes_applied} fixed
                  </span>
                )}
              </div>
              
              <div className="flex items-center space-x-3 text-xs text-gray-500">
                <span>{run.files_audited} files</span>
                <span className="flex items-center">
                  <Clock className="h-3 w-3 mr-1" />
                  {run.duration_seconds}s
                </span>
                <span className="bg-gray-100 px-2 py-1 rounded text-xs">
                  {run.model.replace('qwen2.5-coder:', 'qwen:')}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
