import { motion } from 'framer-motion'
import { Link2, ShieldCheck, ShieldAlert, Hash, Clock } from 'lucide-react'

export default function AuditTrailPanel({ chainLink = {}, metrics = {} }) {
  const hasChain = chainLink && chainLink.chain_hash

  return (
    <div className="space-y-6">
      {/* Chain status */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card rounded-xl p-6">
        <div className="flex items-center space-x-4 mb-5">
          <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${hasChain ? 'bg-success/15 glow-cyan' : 'bg-accent/15'}`}>
            {hasChain ? <ShieldCheck size={24} className="text-success" /> : <ShieldAlert size={24} className="text-muted" />}
          </div>
          <div>
            <h3 className="text-white font-semibold text-lg">
              {hasChain ? 'Audit Chain Verified' : 'No Audit Chain'}
            </h3>
            <p className="text-muted text-sm">
              {hasChain ? 'Tamper-evident Merkle chain is active. Each audit cryptographically links to the previous.' : 'Run an audit to initialize the tamper-evident chain.'}
            </p>
          </div>
        </div>

        {hasChain && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-surface-600/50 rounded-lg p-4 border border-accent/10">
              <div className="flex items-center space-x-2 mb-2">
                <Hash size={14} className="text-accent-light" />
                <span className="text-[10px] uppercase tracking-wider text-muted font-semibold">Chain Hash</span>
              </div>
              <code className="text-xs text-accent-light font-mono break-all">{chainLink.chain_hash?.slice(0, 24)}...</code>
            </div>
            <div className="bg-surface-600/50 rounded-lg p-4 border border-accent/10">
              <div className="flex items-center space-x-2 mb-2">
                <Link2 size={14} className="text-pink-light" />
                <span className="text-[10px] uppercase tracking-wider text-muted font-semibold">Previous Hash</span>
              </div>
              <code className="text-xs text-pink-light font-mono break-all">
                {chainLink.previous_hash === 'genesis' ? '<genesis>' : `${chainLink.previous_hash?.slice(0, 24)}...`}
              </code>
            </div>
            <div className="bg-surface-600/50 rounded-lg p-4 border border-accent/10">
              <div className="flex items-center space-x-2 mb-2">
                <Clock size={14} className="text-warning" />
                <span className="text-[10px] uppercase tracking-wider text-muted font-semibold">Timestamp</span>
              </div>
              <span className="text-xs text-white">{chainLink.timestamp?.replace('T', ' ').replace('Z', ' UTC')}</span>
            </div>
            <div className="bg-surface-600/50 rounded-lg p-4 border border-accent/10">
              <div className="flex items-center space-x-2 mb-2">
                <ShieldCheck size={14} className="text-success" />
                <span className="text-[10px] uppercase tracking-wider text-muted font-semibold">Run ID</span>
              </div>
              <code className="text-xs text-success font-mono">{chainLink.run_id || 'N/A'}</code>
            </div>
          </div>
        )}
      </motion.div>

      {/* Run metrics */}
      {metrics && metrics.run_id && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }} className="glass-card rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-accent/10">
            <h3 className="text-sm font-semibold text-white">Orchestration Metrics</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-0">
            {[
              { label: 'Files Discovered', value: metrics.files_discovered, color: 'text-accent-light' },
              { label: 'Files Analyzed', value: metrics.files_analyzed, color: 'text-accent-light' },
              { label: 'Total LOC', value: (metrics.total_loc || 0).toLocaleString(), color: 'text-white' },
              { label: 'Total Duration', value: `${((metrics.total_duration_ms || 0) / 1000).toFixed(1)}s`, color: 'text-warning' },
              { label: 'Safe to Push', value: metrics.safe_to_push, color: 'text-success' },
              { label: 'Unsafe', value: metrics.unsafe_to_push, color: 'text-pink' },
              { label: 'Avg Duration', value: `${((metrics.avg_duration_ms || 0) / 1000).toFixed(1)}s`, color: 'text-muted' },
              { label: 'Models Used', value: Object.keys(metrics.models_per_file || {}).length, color: 'text-accent-light' },
            ].map((item) => (
              <div key={item.label} className="px-5 py-4 border-b border-r border-accent/5">
                <p className="text-[10px] uppercase tracking-wider text-muted font-semibold mb-1">{item.label}</p>
                <p className={`text-lg font-bold ${item.color}`}>{item.value}</p>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Chain explanation */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="glass-card rounded-xl p-5">
        <h4 className="text-sm font-semibold text-white mb-2">How the Audit Chain Works</h4>
        <p className="text-xs text-muted leading-relaxed">
          Each audit run generates a SHA-256 hash of its results. This hash is combined with the previous run's chain hash
          to create a Merkle chain. If any historical audit is deleted, modified, or reordered, the chain breaks - providing
          cryptographic proof of audit integrity. This is DockDesk's tamper-evident compliance layer.
        </p>
        <div className="mt-3 flex items-center space-x-2">
          <div className="flex items-center space-x-1.5">
            <div className="w-6 h-6 rounded bg-accent/20 flex items-center justify-center"><span className="text-[10px] text-accent-light font-mono">H1</span></div>
            <span className="text-muted text-xs">&rarr;</span>
            <div className="w-6 h-6 rounded bg-accent/20 flex items-center justify-center"><span className="text-[10px] text-accent-light font-mono">H2</span></div>
            <span className="text-muted text-xs">&rarr;</span>
            <div className="w-6 h-6 rounded bg-pink/20 flex items-center justify-center"><span className="text-[10px] text-pink-light font-mono">H3</span></div>
            <span className="text-muted text-xs">&rarr;</span>
            <div className="w-6 h-6 rounded bg-success/20 glow-cyan flex items-center justify-center"><span className="text-[10px] text-success font-mono font-bold">Hn</span></div>
          </div>
          <span className="text-[10px] text-muted ml-2">&larr; each link = sha256(prev_hash + content_hash)</span>
        </div>
      </motion.div>
    </div>
  )
}
