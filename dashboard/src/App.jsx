import { useState, useEffect } from 'react'
import Sidebar from './components/Sidebar'
import StatsCards from './components/StatsCards'
import AuditTimeline from './components/AuditTimeline'
import RiskChart from './components/RiskChart'
import ModelUsage from './components/ModelUsage'
import RecentRuns from './components/RecentRuns'
import FileResults from './components/FileResults'
import PushSafety from './components/PushSafety'
import AuditTree from './components/AuditTree'
import ExportPanel from './components/ExportPanel'
import DiscordPanel from './components/DiscordPanel'
import AnomaliesPanel from './components/AnomaliesPanel'
import { RefreshCw, WifiOff, Download, FileSpreadsheet } from 'lucide-react'

function App() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState(null)
  const [activeView, setActiveView] = useState('overview')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

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

  // Quick Excel export from header
  const handleQuickExcelExport = async () => {
    if (!data) return
    try {
      const XLSX = await import('xlsx')
      const wb = XLSX.utils.book_new()

      const files = data.latest_run_files || []
      const headers = ['File', 'Status', 'Risk', 'Safe to Push', 'Summary', 'Code Model', 'Duration (s)']
      const rows = files.map(f => [
        f.file, f.status, f.risk, f.safe_to_push ? 'YES' : 'NO',
        f.summary || '', f.code_model || '', (f.duration_ms / 1000).toFixed(1),
      ])
      const sheet = XLSX.utils.aoa_to_sheet([headers, ...rows])
      sheet['!cols'] = [{ wch: 40 }, { wch: 10 }, { wch: 10 }, { wch: 12 }, { wch: 60 }, { wch: 22 }, { wch: 12 }]
      XLSX.utils.book_append_sheet(wb, sheet, 'Audit Results')

      XLSX.writeFile(wb, `DockDesk_Quick_Export_${new Date().toISOString().slice(0, 10)}.xlsx`)
    } catch (err) {
      console.error('Quick export failed:', err)
    }
  }

  const mainMargin = sidebarCollapsed ? 'ml-16' : 'ml-56'

  if (loading && !data) {
    return (
      <div className="min-h-screen bg-surface-700 flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 rounded-xl bg-accent/20 flex items-center justify-center mx-auto mb-4">
            <RefreshCw size={24} className="text-accent animate-spin" />
          </div>
          <p className="text-muted text-sm">Loading audit data…</p>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-surface-700 flex items-center justify-center">
        <div className="text-center max-w-md mx-auto px-6">
          <div className="w-16 h-16 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-5">
            <WifiOff size={28} className="text-accent" />
          </div>
          <h2 className="text-xl font-semibold text-white mb-2">No Audit Data</h2>
          <p className="text-muted text-sm mb-6">Run your first audit to see results here.</p>
          <div className="bg-surface-800 rounded-xl p-4 text-left border border-white/5">
            <code className="text-accent text-sm font-mono">$ dockdesk audit --workspace /path/to/project</code>
          </div>
          <p className="text-muted text-xs mt-4">Auto-refreshes every 30 seconds</p>
        </div>
      </div>
    )
  }

  const { stats, timeline, recent_runs, dual_model, latest_run_files, audit_tree, available_models, models_used_this_run } = data

  const renderContent = () => {
    switch (activeView) {
      case 'tree':
        return <AuditTree tree={audit_tree} files={latest_run_files || []} />
      case 'files':
        return <FileResults files={latest_run_files || []} />
      case 'timeline':
        return <AuditTimeline timeline={timeline || []} />
      case 'safety':
        return <PushSafety files={latest_run_files || []} />
      case 'anomalies':
        return <AnomaliesPanel metrics={data.orchestration_metrics || {}} />
      case 'models':
        return (
          <ModelUsage
            modelUsage={stats?.model_usage || {}}
            dualModel={dual_model}
            modelsUsed={models_used_this_run}
            availableModels={available_models}
            latestFiles={latest_run_files || []}
          />
        )
      case 'runs':
        return <RecentRuns runs={recent_runs || []} />
      case 'reports':
        return <ExportPanel data={data} />
      case 'discord':
        return <DiscordPanel />
      case 'overview':
      default:
        return (
          <div className="space-y-6">
            <StatsCards stats={stats} modelsUsed={models_used_this_run} files={latest_run_files || []} />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <PushSafety files={latest_run_files || []} />
              <RiskChart riskTotals={stats?.risk_totals || { HIGH: 0, MEDIUM: 0, LOW: 0 }} />
            </div>
            {/* Audit Tree on overview */}
            {(audit_tree || (latest_run_files && latest_run_files.length > 0)) && (
              <AuditTree tree={audit_tree} files={latest_run_files || []} />
            )}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <AuditTimeline timeline={timeline || []} />
              <ModelUsage
                modelUsage={stats?.model_usage || {}}
                dualModel={dual_model}
                modelsUsed={models_used_this_run}
                availableModels={available_models}
                latestFiles={latest_run_files || []}
              />
            </div>
            {latest_run_files && latest_run_files.length > 0 && (
              <FileResults files={latest_run_files} />
            )}
            <RecentRuns runs={recent_runs || []} />
          </div>
        )
    }
  }

  return (
    <div className="min-h-screen bg-surface-700">
      <Sidebar
        activeView={activeView}
        onNavigate={setActiveView}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      <div className={`${mainMargin} transition-all duration-300`}>
        {/* Top bar */}
        <header className="sticky top-0 z-20 bg-surface-700/80 backdrop-blur-md border-b border-white/5">
          <div className="flex items-center justify-between px-6 h-14">
            <div className="flex items-center space-x-3">
              <h1 className="text-sm font-medium text-white capitalize">
                {activeView === 'overview' ? 'Dashboard' :
                 activeView === 'tree' ? 'Audit Tree' :
                 activeView === 'reports' ? 'Export Reports' :
                 activeView === 'discord' ? 'Discord Integration' :
                 activeView.replace('-', ' ')}
              </h1>
              {dual_model && (
                <span className="text-xs text-muted bg-white/5 px-2.5 py-1 rounded-full">
                  {dual_model.code_model} + {dual_model.reasoning_model}
                </span>
              )}
            </div>

            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-1.5 text-xs text-muted">
                <span className="w-1.5 h-1.5 rounded-full bg-success pulse-dot" />
                <span>Live</span>
              </div>

              {lastRefresh && (
                <span className="text-xs text-muted">
                  {lastRefresh.toLocaleTimeString()}
                </span>
              )}

              <button
                onClick={loadData}
                disabled={loading}
                className="flex items-center space-x-1.5 text-xs text-muted hover:text-white bg-white/5 hover:bg-white/10 px-3 py-1.5 rounded-lg transition"
              >
                <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
                <span>Refresh</span>
              </button>

              <button
                onClick={handleQuickExcelExport}
                className="flex items-center space-x-1.5 text-xs text-muted hover:text-white bg-white/5 hover:bg-white/10 px-3 py-1.5 rounded-lg transition print:hidden"
                title="Quick Excel Export"
              >
                <FileSpreadsheet size={12} />
                <span>Export Excel</span>
              </button>

              <button
                onClick={() => window.print()}
                className="flex items-center space-x-1.5 text-xs text-muted hover:text-white bg-white/5 hover:bg-white/10 px-3 py-1.5 rounded-lg transition print:hidden"
                title="Export as PDF (Ctrl+P)"
              >
                <Download size={12} />
                <span>Export PDF</span>
              </button>
            </div>
          </div>
        </header>

        {/* Content */}
        <main className="p-6">
          {renderContent()}
        </main>
      </div>
    </div>
  )
}

export default App
