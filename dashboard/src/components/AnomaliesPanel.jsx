import { motion } from 'framer-motion'
import { AlertTriangle, Activity, Zap, BarChart3 } from 'lucide-react'

export default function AnomaliesPanel({ metrics = {} }) {
  const riskDist = metrics.risk_distribution || {}
  const passFail = metrics.pass_fail_distribution || {}
  const modelsUsed = metrics.models_per_file || {}
  const totalDuration = metrics.total_duration_ms || 0
  const avgDuration = metrics.avg_duration_ms || 0
  const filesAnalyzed = metrics.files_analyzed || 0

  // Detect anomalies
  const anomalies = []
  if ((riskDist.HIGH || 0) > (filesAnalyzed * 0.3)) {
    anomalies.push({ level: 'critical', msg: `${riskDist.HIGH} HIGH risk files (>${Math.round(filesAnalyzed * 0.3)} threshold)`, icon: AlertTriangle })
  }
  if (avgDuration > 30000) {
    anomalies.push({ level: 'warning', msg: `Average duration ${(avgDuration / 1000).toFixed(1)}s exceeds 30s threshold`, icon: Activity })
  }
  if ((passFail.ERROR || 0) > 0) {
    anomalies.push({ level: 'warning', msg: `${passFail.ERROR} files had errors during analysis`, icon: Zap })
  }
  if (Object.keys(modelsUsed).length > 3) {
    anomalies.push({ level: 'info', msg: `${Object.keys(modelsUsed).length} models used - check for rotation issues`, icon: BarChart3 })
  }

  const levelColors = {
    critical: { bg: 'bg-pink/15', border: 'border-pink/30', text: 'text-pink', icon: 'text-pink' },
    warning: { bg: 'bg-warning/15', border: 'border-warning/30', text: 'text-warning', icon: 'text-warning' },
    info: { bg: 'bg-accent/15', border: 'border-accent/30', text: 'text-accent-light', icon: 'text-accent-light' },
  }

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      <div className="glass-card rounded-xl p-5">
        <div className="flex items-center space-x-2 mb-4">
          <AlertTriangle size={16} className="text-warning" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Detected Anomalies</h3>
        </div>

        {anomalies.length === 0 ? (
          <div className="text-center py-6">
            <div className="w-12 h-12 rounded-xl bg-success/15 flex items-center justify-center mx-auto mb-3">
              <Zap size={20} className="text-success" />
            </div>
            <p className="text-sm text-success font-medium">No anomalies detected</p>
            <p className="text-xs text-muted mt-1">All metrics within normal range.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {anomalies.map((a, i) => {
              const colors = levelColors[a.level] || levelColors.info
              const Icon = a.icon
              return (
                <motion.div key={i} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.1 }}
                  className={`flex items-start space-x-3 p-3 rounded-lg ${colors.bg} border ${colors.border}`}>
                  <Icon size={16} className={`${colors.icon} flex-shrink-0 mt-0.5`} />
                  <span className={`text-sm ${colors.text}`}>{a.msg}</span>
                </motion.div>
              )
            })}
          </div>
        )}
      </div>

      {/* Metrics summary */}
      <div className="glass-card rounded-xl p-5">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted mb-4">Pipeline Metrics</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Total Duration', value: `${(totalDuration / 1000).toFixed(1)}s`, color: 'text-accent-light' },
            { label: 'Avg per File', value: `${(avgDuration / 1000).toFixed(1)}s`, color: 'text-accent-light' },
            { label: 'Files Analyzed', value: filesAnalyzed, color: 'text-white' },
            { label: 'Models Used', value: Object.keys(modelsUsed).length, color: 'text-accent-light' },
          ].map(m => (
            <div key={m.label} className="text-center">
              <p className={`text-xl font-bold ${m.color}`}>{m.value}</p>
              <p className="text-[10px] text-muted uppercase tracking-wider mt-1">{m.label}</p>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  )
}
