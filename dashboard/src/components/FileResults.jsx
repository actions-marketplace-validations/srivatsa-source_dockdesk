import { motion } from 'framer-motion'
import { FileText, ChevronDown, ChevronUp, CheckCircle2, XCircle, AlertTriangle, Slash, ShieldCheck, ShieldAlert } from 'lucide-react'
import { useState } from 'react'

const riskStyle = { HIGH: 'risk-high', MEDIUM: 'risk-medium', LOW: 'risk-low' }

export default function FileResults({ files = [] }) {
  const [expanded, setExpanded] = useState(null)

  const getStatusIcon = (status) => {
    switch (status) {
      case 'PASS': return <CheckCircle2 size={14} className="text-success" />
      case 'FAIL': return <XCircle size={14} className="text-pink" />
      case 'SKIP': return <Slash size={14} className="text-muted" />
      case 'ERROR': return <AlertTriangle size={14} className="text-warning" />
      default: return <CheckCircle2 size={14} className="text-success" />
    }
  }

  if (files.length === 0) return null

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-accent/10">
        <h3 className="text-sm font-semibold text-white">File Results ({files.length})</h3>
      </div>
      <div className="divide-y divide-accent/5">
        {files.map((f, i) => {
          const isOpen = expanded === i
          return (
            <div key={i} className="hover:bg-accent/5 transition">
              <button onClick={() => setExpanded(isOpen ? null : i)} className="w-full flex items-center justify-between px-5 py-3 text-left">
                <div className="flex items-center space-x-3 min-w-0">
                  <div className="flex-shrink-0 flex items-center justify-center">
                    {getStatusIcon(f.status)}
                  </div>
                  <span className="text-sm text-white truncate">{f.file}</span>
                  <span className={`text-[10px] font-bold uppercase ${riskStyle[f.risk] || 'text-muted'}`}>{f.risk}</span>
                  {f.author && <span className="text-[10px] text-muted">by {f.author}</span>}
                </div>
                <div className="flex items-center space-x-3 flex-shrink-0">
                  <div className={`flex items-center space-x-1 text-xs ${f.safe_to_push ? 'text-success' : 'text-pink'}`}>
                    {f.safe_to_push ? <ShieldCheck size={12} /> : <ShieldAlert size={12} />}
                    <span>{f.safe_to_push ? 'safe' : 'unsafe'}</span>
                  </div>
                  {isOpen ? <ChevronUp size={14} className="text-muted" /> : <ChevronDown size={14} className="text-muted" />}
                </div>
              </button>
              {isOpen && (
                <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
                  className="px-5 pb-4 text-xs text-muted border-t border-accent/5 pt-3 space-y-1">
                  <p><span className="text-accent-light">Summary:</span> {f.summary || 'No summary'}</p>
                  {f.code_model && <p><span className="text-accent-light">Model:</span> {f.code_model}</p>}
                  {f.duration_ms > 0 && <p><span className="text-accent-light">Duration:</span> {(f.duration_ms / 1000).toFixed(1)}s</p>}
                </motion.div>
              )}
            </div>
          )
        })}
      </div>
    </motion.div>
  )
}

