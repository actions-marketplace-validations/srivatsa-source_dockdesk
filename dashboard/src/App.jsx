import { useState, useEffect } from 'react'
import StatsCards from './components/StatsCards'
import AuditTimeline from './components/AuditTimeline'
import RiskChart from './components/RiskChart'
import ModelUsage from './components/ModelUsage'
import RecentRuns from './components/RecentRuns'
import FileResults from './components/FileResults'
import PushSafety from './components/PushSafety'

const ASCII_LOGO = `
 ____   ___   ____ _  ______  _____ ____  _  __
|  _ \\ / _ \\ / ___| |/ /  _ \\| ____/ ___|| |/ /
| | | | | | | |   | ' /| | | |  _| \\___ \\| ' / 
| |_| | |_| | |___| . \\| |_| | |___ ___) | . \\ 
|____/ \\___/ \\____|_|\\_\\____/|_____|____/|_|\\_\\
`

function App() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState(null)

  const loadData = async () => {
    setLoading(true)
    try {
      const response = await fetch('./dashboard_data.json?t=' + Date.now())
      if (response.ok) {
        const jsonData = await response.json()
        setData(jsonData)
      } else {
        setData(null)
      }
    } catch {
      setData(null)
    } finally {
      setLoading(false)
      setLastRefresh(new Date())
    }
  }

  useEffect(() => { loadData() }, [])

  // Auto-refresh every 30s
  useEffect(() => {
    const interval = setInterval(loadData, 30000)
    return () => clearInterval(interval)
  }, [])

  if (loading && !data) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center font-mono">
        <div className="text-center">
          <pre className="text-white text-xs sm:text-sm mb-6">{ASCII_LOGO}</pre>
          <div className="text-mono-dim text-sm">
            <span className="cursor-blink">_</span> Initializing neural auditor...
          </div>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center font-mono">
        <div className="text-center max-w-lg mx-auto px-6">
          <pre className="text-white text-xs sm:text-sm mb-6">{ASCII_LOGO}</pre>
          <h2 className="text-lg font-bold text-white mb-2">[NO DATA]</h2>
          <p className="text-mono-dim mb-6 text-sm">Run your first audit to populate the dashboard.</p>
          <div className="border border-mono-border p-4 text-left bg-mono-card">
            <code className="text-white text-sm font-mono">$ py auditor_slm.py --skip-rag</code>
          </div>
          <p className="text-mono-dim text-xs mt-4">
            Auto-refresh: 30s interval
          </p>
        </div>
      </div>
    )
  }

  const { stats, timeline, recent_runs, dual_model, latest_run_files } = data

  return (
    <div className="min-h-screen bg-black font-mono">
      {/* Header */}
      <header className="bg-black border-b border-mono-border">
        <div className="max-w-7xl mx-auto px-4 py-3 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <span className="text-white font-bold text-lg tracking-wider">[ DOCKDESK ]</span>
              <div className="hidden sm:block">
                <p className="text-xs text-mono-dim">
                  DUAL-MODEL AUDIT SYSTEM
                  {dual_model && (
                    <span className="ml-2 text-white">
                      // {dual_model.code_model} + {dual_model.reasoning_model}
                    </span>
                  )}
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <button
                onClick={loadData}
                className="text-mono-dim hover:text-white transition text-xs border border-mono-border px-3 py-1 hover:border-white"
                title="Refresh data"
              >
                {loading ? '...' : '[REFRESH]'}
              </button>
              {lastRefresh && (
                <span className="text-xs text-mono-dim">
                  {lastRefresh.toLocaleTimeString()}
                </span>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8 space-y-6">
        <StatsCards stats={stats} />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <PushSafety files={latest_run_files || []} />
          <RiskChart riskTotals={stats?.risk_totals || { HIGH: 0, MEDIUM: 0, LOW: 0 }} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <AuditTimeline timeline={timeline || []} />
          <ModelUsage modelUsage={stats?.model_usage || {}} />
        </div>

        {latest_run_files && latest_run_files.length > 0 && (
          <FileResults files={latest_run_files} />
        )}

        <RecentRuns runs={recent_runs || []} />
      </main>

      <footer className="bg-black border-t border-mono-border mt-8">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
          <p className="text-center text-mono-dim text-xs">
            DOCKDESK v2.0 // DUAL-MODEL AUDITOR // QWEN CODER + DEEPSEEK-R1
          </p>
        </div>
      </footer>
    </div>
  )
}

export default App
