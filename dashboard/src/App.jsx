import { useState, useEffect } from 'react'
import { Shield, GitBranch, Clock, FileText, Zap, AlertTriangle, CheckCircle, XCircle } from 'lucide-react'
import StatsCards from './components/StatsCards'
import AuditTimeline from './components/AuditTimeline'
import RiskChart from './components/RiskChart'
import ModelUsage from './components/ModelUsage'
import RecentRuns from './components/RecentRuns'

// Sample data - replace with actual data from audit_history.jsonl
const SAMPLE_DATA = {
  stats: {
    total_audits: 47,
    total_files_audited: 1243,
    total_fixes_applied: 89,
    average_duration_seconds: 12.4,
    risk_totals: { HIGH: 23, MEDIUM: 156, LOW: 412 },
    model_usage: { 
      "qwen2.5-coder:3b": 32, 
      "qwen2.5-coder:7b": 12, 
      "codellama:7b": 3 
    },
  },
  timeline: [
    { date: "2026-01-28", pass: 12, fail: 3, fixes: 2, model: "qwen2.5-coder:3b", duration: 8.2 },
    { date: "2026-01-29", pass: 8, fail: 5, fixes: 4, model: "qwen2.5-coder:7b", duration: 15.3 },
    { date: "2026-01-30", pass: 15, fail: 2, fixes: 1, model: "qwen2.5-coder:3b", duration: 9.1 },
    { date: "2026-01-31", pass: 10, fail: 4, fixes: 3, model: "qwen2.5-coder:3b", duration: 11.5 },
    { date: "2026-02-01", pass: 18, fail: 1, fixes: 1, model: "qwen2.5-coder:7b", duration: 14.2 },
    { date: "2026-02-02", pass: 14, fail: 3, fixes: 2, model: "qwen2.5-coder:3b", duration: 10.8 },
    { date: "2026-02-03", pass: 20, fail: 2, fixes: 2, model: "qwen2.5-coder:3b", duration: 12.1 },
  ],
  recent_runs: [
    { 
      run_id: "run_20260203_a1b2c3", 
      timestamp: "2026-02-03T14:32:00", 
      model: "qwen2.5-coder:3b",
      files_audited: 22,
      pass_count: 20,
      fail_count: 2,
      fixes_applied: 2,
      duration_seconds: 12.1,
      git_branch: "feature/auth-update"
    },
    { 
      run_id: "run_20260202_d4e5f6", 
      timestamp: "2026-02-02T09:15:00", 
      model: "qwen2.5-coder:3b",
      files_audited: 17,
      pass_count: 14,
      fail_count: 3,
      fixes_applied: 2,
      duration_seconds: 10.8,
      git_branch: "main"
    },
    { 
      run_id: "run_20260201_g7h8i9", 
      timestamp: "2026-02-01T16:45:00", 
      model: "qwen2.5-coder:7b",
      files_audited: 19,
      pass_count: 18,
      fail_count: 1,
      fixes_applied: 1,
      duration_seconds: 14.2,
      git_branch: "develop"
    },
  ]
}

function App() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    // Try to load data from dashboard_data.json (exported from CLI)
    // Falls back to sample data for demo
    async function loadData() {
      try {
        const response = await fetch('./dashboard_data.json')
        if (response.ok) {
          const jsonData = await response.json()
          setData(jsonData)
        } else {
          // Use sample data for demo
          setData(SAMPLE_DATA)
        }
      } catch (e) {
        // Use sample data if file not found
        setData(SAMPLE_DATA)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-red-600">Error loading data: {error}</div>
      </div>
    )
  }

  const { stats, timeline, recent_runs } = data

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Shield className="h-8 w-8 text-blue-600" />
              <div>
                <h1 className="text-2xl font-bold text-gray-900">DockDesk Dashboard</h1>
                <p className="text-sm text-gray-500">Semantic Audit Analytics</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-500">
                Last updated: {new Date().toLocaleString()}
              </span>
              <a 
                href="https://github.com/dockdesk/auditor" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-blue-600 hover:text-blue-800 text-sm"
              >
                Documentation
              </a>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        {/* Stats Cards */}
        <StatsCards stats={stats} />

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-8">
          <AuditTimeline timeline={timeline} />
          <RiskChart riskTotals={stats.risk_totals} />
        </div>

        {/* Bottom Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-8">
          <ModelUsage modelUsage={stats.model_usage} />
          <RecentRuns runs={recent_runs} />
        </div>

        {/* Setup Instructions */}
        <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-blue-900 mb-2">📊 Using Real Data</h3>
          <p className="text-blue-800 mb-4">
            This dashboard is currently showing sample data. To display your actual audit history:
          </p>
          <ol className="list-decimal list-inside space-y-2 text-blue-800">
            <li>Run audits with DockDesk: <code className="bg-blue-100 px-2 py-1 rounded">python auditor_slm.py</code></li>
            <li>Export dashboard data: <code className="bg-blue-100 px-2 py-1 rounded">python auditor_slm.py dashboard --export dashboard_data.json</code></li>
            <li>Copy <code className="bg-blue-100 px-2 py-1 rounded">dashboard_data.json</code> to this dashboard folder</li>
            <li>Refresh this page</li>
          </ol>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-white border-t mt-12">
        <div className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
          <p className="text-center text-gray-500 text-sm">
            DockDesk Neural Auditor • Local-first semantic documentation auditing
          </p>
        </div>
      </footer>
    </div>
  )
}

export default App
