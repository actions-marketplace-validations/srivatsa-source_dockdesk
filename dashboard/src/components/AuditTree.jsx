import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ChevronRight, ChevronDown, Folder, FolderOpen, FileCode,
  CheckCircle, XCircle, AlertTriangle, MinusCircle,
  ShieldCheck, ShieldAlert, Clock, Cpu, ChevronUp
} from 'lucide-react'

const RISK_COLORS = {
  HIGH: { bg: 'bg-pink-500/15', text: 'text-pink-400', border: 'border-pink-500/30', dot: 'bg-pink-500' },
  MEDIUM: { bg: 'bg-yellow-500/15', text: 'text-yellow-400', border: 'border-yellow-500/30', dot: 'bg-yellow-500' },
  LOW: { bg: 'bg-cyan-500/15', text: 'text-cyan-400', border: 'border-cyan-500/30', dot: 'bg-cyan-500' },
  UNKNOWN: { bg: 'bg-slate-500/15', text: 'text-slate-400', border: 'border-slate-500/30', dot: 'bg-slate-500' },
}

const STATUS_ICONS = {
  PASS: { icon: CheckCircle, className: 'text-cyan-400' },
  FAIL: { icon: XCircle, className: 'text-pink-400' },
  ERROR: { icon: AlertTriangle, className: 'text-yellow-400' },
  SKIP: { icon: MinusCircle, className: 'text-slate-500' },
  UNKNOWN: { icon: MinusCircle, className: 'text-slate-500' },
}

function RiskPills({ counts }) {
  if (!counts) return null
  const total = (counts.HIGH || 0) + (counts.MEDIUM || 0) + (counts.LOW || 0)
  if (total === 0) return null
  return (
    <div className="flex items-center space-x-1.5 ml-2">
      {counts.HIGH > 0 && (
        <span className="inline-flex items-center space-x-1 bg-pink-500/15 text-pink-400 text-[10px] font-semibold px-1.5 py-0.5 rounded-full">
          <span className="w-1.5 h-1.5 rounded-full bg-pink-500" /><span>{counts.HIGH}</span>
        </span>
      )}
      {counts.MEDIUM > 0 && (
        <span className="inline-flex items-center space-x-1 bg-yellow-500/15 text-yellow-400 text-[10px] font-semibold px-1.5 py-0.5 rounded-full">
          <span className="w-1.5 h-1.5 rounded-full bg-yellow-500" /><span>{counts.MEDIUM}</span>
        </span>
      )}
      {counts.LOW > 0 && (
        <span className="inline-flex items-center space-x-1 bg-cyan-500/15 text-cyan-400 text-[10px] font-semibold px-1.5 py-0.5 rounded-full">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-500" /><span>{counts.LOW}</span>
        </span>
      )}
    </div>
  )
}

function FileDetail({ node }) {
  const risk = RISK_COLORS[node.risk] || RISK_COLORS.UNKNOWN
  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      className={`mt-2 ml-7 p-3 rounded-lg border ${risk.border} ${risk.bg}`}
    >
      <div className="flex items-center space-x-4 text-[11px] mb-2">
        <span className={`inline-flex items-center space-x-1 ${risk.text}`}>
          <span className={`w-2 h-2 rounded-full ${risk.dot}`} /><span className="font-semibold">{node.risk}</span>
        </span>
        {node.safe_to_push ? (
          <span className="inline-flex items-center space-x-1 text-cyan-400"><ShieldCheck size={12} /><span>Safe to push</span></span>
        ) : (
          <span className="inline-flex items-center space-x-1 text-pink-400"><ShieldAlert size={12} /><span>Unsafe</span></span>
        )}
        <span className="inline-flex items-center space-x-1 text-slate-400"><Clock size={11} /><span>{(node.duration_ms / 1000).toFixed(1)}s</span></span>
        {node.code_model && (
          <span className="inline-flex items-center space-x-1 text-slate-400"><Cpu size={11} /><span className="font-mono">{node.code_model}</span></span>
        )}
      </div>
      {node.summary && <p className="text-xs text-slate-300 mb-2">{node.summary}</p>}
      {node.fix && (
        <div className="mt-2">
          <p className="text-[10px] text-yellow-400 font-semibold uppercase tracking-wider mb-1">Suggested Fix</p>
          <p className="text-xs text-slate-300 font-mono bg-black/20 rounded p-2">{node.fix}</p>
        </div>
      )}
      {node.reasoning && (
        <div className="mt-2">
          <p className="text-[10px] text-purple-400 font-semibold uppercase tracking-wider mb-1">AI Reasoning</p>
          <p className="text-xs text-slate-400 italic">{node.reasoning}</p>
        </div>
      )}
    </motion.div>
  )
}

function TreeNode({ node, depth = 0 }) {
  const [expanded, setExpanded] = useState(depth < 2)
  const [detailOpen, setDetailOpen] = useState(false)

  if (node.type === 'dir') {
    const hasChildren = node.children && node.children.length > 0
    const FolderIcon = expanded ? FolderOpen : Folder
    const highRisk = node.risk_counts?.HIGH || 0
    const dirColor = highRisk > 0 ? 'text-pink-400' : 'text-purple-400'

    return (
      <div className="select-none">
        <button onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center py-1.5 px-2 rounded-md text-left hover:bg-purple-500/[0.08] transition-colors group"
          style={{ paddingLeft: `${depth * 16 + 8}px` }}>
          <span className="mr-1 text-slate-500 transition-transform duration-200">
            {hasChildren ? (expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />) : <span className="w-3.5" />}
          </span>
          <FolderIcon size={16} className={`mr-2 ${dirColor} transition-colors`} />
          <span className="text-sm text-white font-medium">{node.name}</span>
          <RiskPills counts={node.risk_counts} />
          {hasChildren && (
            <span className="ml-auto text-[10px] text-slate-600 group-hover:text-slate-400 transition-colors">{node.children.length} items</span>
          )}
        </button>
        <AnimatePresence>
          {expanded && hasChildren && (
            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="tree-branch">
              {node.children
                .sort((a, b) => {
                  if (a.type !== b.type) return a.type === 'dir' ? -1 : 1
                  const riskOrder = { HIGH: 0, MEDIUM: 1, LOW: 2, UNKNOWN: 3 }
                  const rA = riskOrder[a.risk] ?? riskOrder[a.risk_counts?.HIGH > 0 ? 'HIGH' : 'LOW'] ?? 3
                  const rB = riskOrder[b.risk] ?? riskOrder[b.risk_counts?.HIGH > 0 ? 'HIGH' : 'LOW'] ?? 3
                  return rA - rB
                })
                .map((child, i) => <TreeNode key={`${child.name}-${i}`} node={child} depth={depth + 1} />)}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    )
  }

  const status = STATUS_ICONS[node.status] || STATUS_ICONS.UNKNOWN
  const risk = RISK_COLORS[node.risk] || RISK_COLORS.UNKNOWN
  const StatusIcon = status.icon

  return (
    <div>
      <button onClick={() => setDetailOpen(!detailOpen)}
        className="w-full flex items-center py-1.5 px-2 rounded-md text-left hover:bg-purple-500/[0.08] transition-colors group"
        style={{ paddingLeft: `${depth * 16 + 8}px` }}>
        <span className="mr-1 w-3.5" />
        <FileCode size={14} className="mr-2 text-slate-500" />
        <span className="text-sm text-slate-300 group-hover:text-white transition-colors font-mono">{node.name}</span>
        <div className="flex items-center ml-auto space-x-2">
          <span className={`inline-flex items-center space-x-1 ${risk.bg} ${risk.text} text-[10px] font-semibold px-1.5 py-0.5 rounded-full`}>
            <span className={`w-1.5 h-1.5 rounded-full ${risk.dot}`} /><span>{node.risk}</span>
          </span>
          <StatusIcon size={14} className={status.className} />
          {node.safe_to_push ? <ShieldCheck size={13} className="text-cyan-400" /> : <ShieldAlert size={13} className="text-pink-400" />}
          <span className="text-slate-600">{detailOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}</span>
        </div>
      </button>
      <AnimatePresence>{detailOpen && <FileDetail node={node} />}</AnimatePresence>
    </div>
  )
}

function TreeLegend() {
  return (
    <div className="flex flex-wrap items-center gap-4 mb-4 text-[11px] text-slate-400">
      <span className="font-semibold text-slate-300">Legend:</span>
      <span className="inline-flex items-center space-x-1"><CheckCircle size={12} className="text-cyan-400" /><span>Pass</span></span>
      <span className="inline-flex items-center space-x-1"><XCircle size={12} className="text-pink-400" /><span>Fail</span></span>
      <span className="inline-flex items-center space-x-1"><AlertTriangle size={12} className="text-yellow-400" /><span>Error</span></span>
      <span className="inline-flex items-center space-x-1"><span className="w-2 h-2 rounded-full bg-pink-500" /><span>HIGH</span></span>
      <span className="inline-flex items-center space-x-1"><span className="w-2 h-2 rounded-full bg-yellow-500" /><span>MEDIUM</span></span>
      <span className="inline-flex items-center space-x-1"><span className="w-2 h-2 rounded-full bg-cyan-500" /><span>LOW</span></span>
      <span className="inline-flex items-center space-x-1"><ShieldCheck size={12} className="text-cyan-400" /><span>Safe</span></span>
      <span className="inline-flex items-center space-x-1"><ShieldAlert size={12} className="text-pink-400" /><span>Unsafe</span></span>
    </div>
  )
}

export default function AuditTree({ tree, files }) {
  const treeData = tree || buildTreeFromFiles(files || [])

  if (!treeData || (!treeData.children?.length && !files?.length)) {
    return (
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass-card rounded-xl p-6">
        <h3 className="text-sm font-semibold text-white mb-4">Audit Tree</h3>
        <p className="text-muted text-xs">No audit data yet. Run an audit to see the file tree.</p>
      </motion.div>
    )
  }

  const totalFiles = countFiles(treeData)
  const highCount = treeData.risk_counts?.HIGH || 0
  const medCount = treeData.risk_counts?.MEDIUM || 0
  const lowCount = treeData.risk_counts?.LOW || 0

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card glass-card-hover rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-purple-500/20 to-pink-500/20 flex items-center justify-center">
            <Folder size={14} className="text-purple-400" />
          </div>
          <h3 className="text-sm font-semibold text-white">Audit Tree</h3>
          <span className="text-[10px] text-purple-300 bg-purple-500/10 border border-purple-500/20 px-2 py-0.5 rounded-full">{totalFiles} files</span>
        </div>
        <div className="flex items-center space-x-2">
          {highCount > 0 && <span className="text-[11px] risk-high font-semibold">{highCount} HIGH</span>}
          {medCount > 0 && <span className="text-[11px] risk-medium font-semibold">{medCount} MED</span>}
          {lowCount > 0 && <span className="text-[11px] risk-low font-semibold">{lowCount} LOW</span>}
        </div>
      </div>
      <TreeLegend />
      <div className="border border-purple-500/10 rounded-lg glass-card p-2 max-h-[600px] overflow-y-auto">
        <TreeNode node={treeData} depth={0} />
      </div>
    </motion.div>
  )
}

function countFiles(node) {
  if (!node) return 0
  if (node.type === 'file') return 1
  return (node.children || []).reduce((acc, child) => acc + countFiles(child), 0)
}

function buildTreeFromFiles(files) {
  const root = { name: 'project', type: 'dir', children: [], risk_counts: { HIGH: 0, MEDIUM: 0, LOW: 0 } }
  for (const f of files) {
    const parts = (f.file || '').replace(/\\/g, '/').split('/')
    let current = root
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i]
      if (i === parts.length - 1) {
        current.children.push({
          name: part, type: 'file', path: f.file, status: f.status || 'UNKNOWN', risk: f.risk || 'UNKNOWN',
          safe_to_push: f.safe_to_push ?? false, summary: f.summary || '', fix: '', reasoning: '',
          code_model: f.code_model || '', reasoning_model: f.reasoning_model || '', duration_ms: f.duration_ms || 0,
        })
        const risk = f.risk
        if (risk === 'HIGH' || risk === 'MEDIUM' || risk === 'LOW') {
          root.risk_counts[risk]++
          let ancestor = root
          for (let j = 0; j < i; j++) {
            const ancestorChild = ancestor.children.find(c => c.type === 'dir' && c.name === parts[j])
            if (ancestorChild) { ancestorChild.risk_counts[risk] = (ancestorChild.risk_counts[risk] || 0) + 1; ancestor = ancestorChild }
          }
        }
      } else {
        let dirNode = current.children.find(c => c.type === 'dir' && c.name === part)
        if (!dirNode) { dirNode = { name: part, type: 'dir', children: [], risk_counts: { HIGH: 0, MEDIUM: 0, LOW: 0 } }; current.children.push(dirNode) }
        current = dirNode
      }
    }
  }
  return root
}
