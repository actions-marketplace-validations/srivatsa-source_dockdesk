import { motion } from 'framer-motion'
import { Play, CheckCircle2, XCircle, Clock, GitBranch, Cpu, Award } from 'lucide-react'

export default function PipelinePanel({ pipeline }) {
  const total = pipeline?.total_runs || 0
  const rate = pipeline?.success_rate || 0
  const avgDur = pipeline?.average_duration || 0
  const runs = pipeline?.runs || []

  // Color mappings based on success rate
  const rateColor = rate >= 80 ? 'text-success' : rate >= 50 ? 'text-yellow-400' : 'text-error'
  const rateBg = rate >= 80 ? 'bg-success/10 border-success/20' : rate >= 50 ? 'bg-yellow-400/10 border-yellow-400/20' : 'bg-error/10 border-error/20'

  return (
    <div className="space-y-6">
      {/* Top Banner / KPI Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-5 rounded-2xl border border-accent/10 relative overflow-hidden"
        >
          <div className="absolute top-0 right-0 w-24 h-24 bg-accent/5 rounded-full blur-2xl pointer-events-none" />
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted font-medium uppercase tracking-wider">Total Pipeline Runs</p>
              <h3 className="text-3xl font-extrabold text-white mt-1.5 font-mono">{total}</h3>
            </div>
            <div className="w-12 h-12 rounded-xl bg-accent/10 border border-accent/20 flex items-center justify-center text-accent-light">
              <Play size={20} />
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className={`glass-card p-5 rounded-2xl border ${rateBg} relative overflow-hidden`}
        >
          <div className="absolute top-0 right-0 w-24 h-24 bg-white/5 rounded-full blur-2xl pointer-events-none" />
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted font-medium uppercase tracking-wider">Success Rate</p>
              <h3 className={`text-3xl font-extrabold mt-1.5 font-mono ${rateColor}`}>{rate}%</h3>
            </div>
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${rateColor} bg-white/5 border border-white/10`}>
              <Award size={20} />
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glass-card p-5 rounded-2xl border border-accent/10 relative overflow-hidden"
        >
          <div className="absolute top-0 right-0 w-24 h-24 bg-pink/5 rounded-full blur-2xl pointer-events-none" />
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted font-medium uppercase tracking-wider">Average Duration</p>
              <h3 className="text-3xl font-extrabold text-white mt-1.5 font-mono">{avgDur}s</h3>
            </div>
            <div className="w-12 h-12 rounded-xl bg-pink/10 border border-pink/20 flex items-center justify-center text-pink-light">
              <Clock size={20} />
            </div>
          </div>
        </motion.div>
      </div>

      {/* Main Runs Table */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="glass-card rounded-2xl border border-accent/10 overflow-hidden"
      >
        <div className="px-6 py-4 border-b border-accent/10 flex items-center justify-between">
          <h3 className="font-semibold text-white text-sm">CI/CD Pipeline Run Registry</h3>
          <span className="text-[10px] text-muted bg-accent/5 border border-accent/10 px-2 py-0.5 rounded font-mono">
            SQLite Powered
          </span>
        </div>

        {runs.length === 0 ? (
          <div className="p-8 text-center">
            <Play size={36} className="text-muted/30 mx-auto mb-3" />
            <p className="text-sm text-muted">No CI/CD runs registered in this repository yet.</p>
            <p className="text-xs text-muted/60 mt-1">Run an audit with the <code className="text-accent-light font-mono">--ci</code> flag to start logging.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-accent/5 text-[10px] uppercase text-muted tracking-wider bg-accent/5">
                  <th className="py-3 px-6">Timestamp</th>
                  <th className="py-3 px-6">Run ID</th>
                  <th className="py-3 px-6">Branch</th>
                  <th className="py-3 px-6">Commit</th>
                  <th className="py-3 px-6">Status</th>
                  <th className="py-3 px-6">Quality Stats</th>
                  <th className="py-3 px-6">Duration</th>
                  <th className="py-3 px-6">Model</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-accent/5">
                {runs.map((r, i) => {
                  const passed = r.status === 'PASS'
                  return (
                    <tr key={i} className="hover:bg-accent/5 transition-colors group">
                      <td className="py-3 px-6 text-muted font-mono whitespace-nowrap">
                        {r.timestamp?.slice(0, 19).replace('T', ' ')}
                      </td>
                      <td className="py-3 px-6 font-mono text-accent-light group-hover:text-white transition-colors">
                        {r.run_id}
                      </td>
                      <td className="py-3 px-6 whitespace-nowrap">
                        <div className="flex items-center space-x-1 text-white">
                          <GitBranch size={12} className="text-accent" />
                          <span>{r.branch}</span>
                        </div>
                      </td>
                      <td className="py-3 px-6 text-muted font-mono whitespace-nowrap">
                        {r.commit}
                      </td>
                      <td className="py-3 px-6 whitespace-nowrap">
                        <div className="flex items-center space-x-1.5">
                          {passed ? (
                            <>
                              <CheckCircle2 size={13} className="text-success" />
                              <span className="text-success font-semibold uppercase">Passed</span>
                            </>
                          ) : (
                            <>
                              <XCircle size={13} className="text-error" />
                              <span className="text-error font-semibold uppercase">Failed</span>
                            </>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-6 whitespace-nowrap">
                        <div className="flex items-center space-x-2">
                          <span className="bg-success/15 text-success font-semibold px-2 py-0.5 rounded text-[10px]">
                            {r.pass_count} Pass
                          </span>
                          {r.fail_count > 0 && (
                            <span className="bg-error/15 text-error font-semibold px-2 py-0.5 rounded text-[10px]">
                              {r.fail_count} Fail
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-6 font-mono text-muted whitespace-nowrap">
                        {r.duration.toFixed(2)}s
                      </td>
                      <td className="py-3 px-6 whitespace-nowrap">
                        <div className="flex items-center space-x-1 text-muted">
                          <Cpu size={12} className="text-pink/70" />
                          <span className="font-mono text-[10px]">{r.model || 'N/A'}</span>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </motion.div>
    </div>
  )
}
