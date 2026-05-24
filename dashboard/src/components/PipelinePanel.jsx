import { motion } from 'framer-motion'
import { Play, CheckCircle2, XCircle, Clock, GitBranch, Cpu, Award } from 'lucide-react'

export function DNAPipelineStrand({ runs }) {
  const displayRuns = [...runs].reverse().slice(-10) // Show last 10 runs as DNA base pairs
  
  // Helix dimensions
  const height = 450
  const width = 180
  const padding = 30
  const step = (height - padding * 2) / Math.max(1, displayRuns.length - 1)
  
  return (
    <div className="glass-card p-6 rounded-2xl border border-accent/10 bg-surface-700/80 relative overflow-hidden h-full flex flex-col justify-between">
      <div className="absolute top-0 right-0 w-32 h-32 bg-accent/5 rounded-full blur-3xl pointer-events-none" />
      <div>
        <h4 className="text-sm font-semibold text-white mb-2 tracking-wide flex items-center space-x-2">
          <span className="w-2.5 h-2.5 rounded-full bg-accent-light animate-ping" />
          <span>Pipeline DNA Helix</span>
        </h4>
        <p className="text-[11px] text-muted mb-4">
          Visualizing repository health. Red rungs flag failing audits.
        </p>
      </div>

      <div className="flex-1 flex justify-center items-center py-4 relative">
        <svg width={width} height={height} className="overflow-visible">
          <defs>
            {/* Bright neon glow filters */}
            <filter id="glow-green" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
            <filter id="glow-red" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
            <linearGradient id="grad-green" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#00FF87" stopOpacity="0.4" />
              <stop offset="50%" stopColor="#00FF87" stopOpacity="1" />
              <stop offset="100%" stopColor="#00FF87" stopOpacity="0.4" />
            </linearGradient>
            <linearGradient id="grad-red" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#FF007F" stopOpacity="0.4" />
              <stop offset="50%" stopColor="#FF007F" stopOpacity="1" />
              <stop offset="100%" stopColor="#FF007F" stopOpacity="0.4" />
            </linearGradient>
          </defs>

          {/* DNA Backbones */}
          {Array.from({ length: 60 }).map((_, stepIdx) => {
            const y = padding + (stepIdx / 59) * (height - padding * 2)
            const angle1 = (stepIdx * 0.25)
            const angle2 = (stepIdx * 0.25) + Math.PI
            
            const x1 = (width / 2) + Math.sin(angle1) * 45
            const x2 = (width / 2) + Math.sin(angle2) * 45
            
            const nextY = padding + ((stepIdx + 1) / 59) * (height - padding * 2)
            const nextAngle1 = ((stepIdx + 1) * 0.25)
            const nextAngle2 = ((stepIdx + 1) * 0.25) + Math.PI
            const nextX1 = (width / 2) + Math.sin(nextAngle1) * 45
            const nextX2 = (width / 2) + Math.sin(nextAngle2) * 45

            if (stepIdx === 59) return null

            return (
              <g key={stepIdx} className="opacity-40">
                <line x1={x1} y1={y} x2={nextX1} y2={nextY} stroke="#8A2BE2" strokeWidth="1.5" />
                <line x1={x2} y1={y} x2={nextX2} y2={nextY} stroke="#DA70D6" strokeWidth="1.5" />
              </g>
            )
          })}

          {/* DNA Base Pairs / Pipeline Runs */}
          {displayRuns.map((run, idx) => {
            const y = padding + idx * step
            const angle = (idx * 0.8) // Twist factor
            const isPass = run.status === 'PASS'
            
            const x1 = (width / 2) + Math.sin(angle) * 45
            const x2 = (width / 2) + Math.sin(angle + Math.PI) * 45
            const grad = isPass ? 'url(#grad-green)' : 'url(#grad-red)'
            const glowFilter = isPass ? 'url(#glow-green)' : 'url(#glow-red)'
            const color = isPass ? '#00FF87' : '#FF007F'

            return (
              <g key={run.run_id} className="cursor-pointer group">
                {/* Connecting Rung */}
                <line
                  x1={x1}
                  y1={y}
                  x2={x2}
                  y2={y}
                  stroke={grad}
                  strokeWidth="3.5"
                  className="transition-all duration-300 group-hover:stroke-white"
                  filter={glowFilter}
                />

                {/* Left Node */}
                <circle
                  cx={x1}
                  cy={y}
                  r="5"
                  fill={color}
                  className="transition-all duration-300 group-hover:r-7"
                  filter={glowFilter}
                />

                {/* Right Node */}
                <circle
                  cx={x2}
                  cy={y}
                  r="5"
                  fill={color}
                  className="transition-all duration-300 group-hover:r-7"
                  filter={glowFilter}
                />

                {/* Target/Focus Ring for Hover */}
                <circle
                  cx={width / 2}
                  cy={y}
                  r="18"
                  fill="transparent"
                  className="group-hover:fill-accent/10 transition-colors"
                />
                
                {/* Embedded status details for tooltips */}
                <foreignObject x="-10" y={y - 8} width="200" height="1">
                  <div className="absolute left-[165px] top-[-30px] opacity-0 group-hover:opacity-100 pointer-events-none transition-all duration-300 bg-surface-900 border border-accent/20 rounded-xl p-3 shadow-2xl z-45 w-56">
                    <div className="flex items-center space-x-1.5 mb-1.5">
                      <span className={`w-2 h-2 rounded-full ${isPass ? 'bg-success' : 'bg-error animate-pulse'}`} />
                      <span className={`text-[10px] font-bold uppercase tracking-wider ${isPass ? 'text-success' : 'text-error'}`}>
                        {isPass ? 'PASSED AUDIT' : 'FLAGGED AUDIT'}
                      </span>
                    </div>
                    <div className="text-[10px] text-white font-mono truncate mb-1">ID: {run.run_id}</div>
                    <div className="text-[10px] text-muted font-mono mb-1">Branch: {run.branch || 'N/A'}</div>
                    <div className="text-[10px] text-muted font-mono mb-1">Commit: {run.commit?.slice(0, 7) || 'N/A'}</div>
                    <div className="text-[10px] text-muted font-mono">Issues: {run.fail_count} flagged</div>
                  </div>
                </foreignObject>
              </g>
            )
          })}
        </svg>
      </div>

      <div className="text-[10px] text-muted text-center pt-2 border-t border-accent/5">
        Hover over the DNA rungs to see audit markers.
      </div>
    </div>
  )
}

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

      {/* Main Content: Registry Table & DNA Strand Side-by-Side */}
      {runs.length === 0 ? (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="glass-card rounded-2xl border border-accent/10 p-8 text-center"
        >
          <Play size={36} className="text-muted/30 mx-auto mb-3" />
          <p className="text-sm text-muted">No CI/CD runs registered in this repository yet.</p>
          <p className="text-xs text-muted/60 mt-1">Run an audit with the <code className="text-accent-light font-mono">--ci</code> flag to start logging.</p>
        </motion.div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Runs Table on Left (2/3 width) */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="lg:col-span-2 glass-card rounded-2xl border border-accent/10 overflow-hidden"
          >
            <div className="px-6 py-4 border-b border-accent/10 flex items-center justify-between">
              <h3 className="font-semibold text-white text-sm">CI/CD Pipeline Run Registry</h3>
              <span className="text-[10px] text-muted bg-accent/5 border border-accent/10 px-2 py-0.5 rounded font-mono">
                SQLite Powered
              </span>
            </div>
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
          </motion.div>

          {/* DNA Double-Helix Strand on Right (1/3 width) */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
            className="lg:col-span-1"
          >
            <DNAPipelineStrand runs={runs} />
          </motion.div>
        </div>
      )}
    </div>
  )
}
