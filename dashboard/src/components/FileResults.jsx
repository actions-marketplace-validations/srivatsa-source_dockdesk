import { CheckCircle, XCircle, MinusCircle, ShieldCheck, ShieldAlert, FileCode } from 'lucide-react'

const riskBadge = {
  HIGH: 'bg-danger-muted text-danger',
  MEDIUM: 'bg-warning-muted text-warning',
  LOW: 'bg-success-muted text-success',
}

export default function FileResults({ files }) {
  return (
    <div className="bg-surface-600 border border-white/5 rounded-xl p-6">
      <div className="flex items-center space-x-2 mb-4">
        <FileCode size={16} className="text-info" />
        <h3 className="text-sm font-semibold text-white">File Results — Latest Run</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-white/5 text-muted uppercase tracking-wider text-[10px]">
              <th className="text-left py-2.5 pr-4">File</th>
              <th className="text-center py-2.5 px-2">Status</th>
              <th className="text-center py-2.5 px-2">Risk</th>
              <th className="text-center py-2.5 px-2">Push</th>
              <th className="text-right py-2.5 px-2">Time</th>
              <th className="text-left py-2.5 pl-4">Summary</th>
            </tr>
          </thead>
          <tbody>
            {files.map((f, i) => (
              <tr key={i} className="border-b border-white/[0.03] hover:bg-white/[0.03] transition-colors">
                <td className="py-2.5 pr-4">
                  <span className="text-white font-mono text-[11px]">
                    {f.file.length > 35 ? '...' + f.file.slice(-32) : f.file}
                  </span>
                </td>
                <td className="text-center py-2.5 px-2">
                  {f.status === 'PASS' ? (
                    <CheckCircle size={14} className="text-success mx-auto" />
                  ) : f.status === 'FAIL' ? (
                    <XCircle size={14} className="text-danger mx-auto" />
                  ) : f.status === 'SKIP' ? (
                    <MinusCircle size={14} className="text-muted mx-auto" />
                  ) : (
                    <span className="text-muted">{f.status || '?'}</span>
                  )}
                </td>
                <td className="text-center py-2.5 px-2">
                  <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${riskBadge[f.risk] || 'bg-surface-400 text-muted'}`}>
                    {f.risk}
                  </span>
                </td>
                <td className="text-center py-2.5 px-2">
                  {f.safe_to_push ? (
                    <ShieldCheck size={14} className="text-success mx-auto" />
                  ) : (
                    <ShieldAlert size={14} className="text-danger mx-auto" />
                  )}
                </td>
                <td className="text-right py-2.5 px-2 text-muted font-mono">
                  {(f.duration_ms / 1000).toFixed(1)}s
                </td>
                <td className="py-2.5 pl-4">
                  <span className="text-muted line-clamp-1">
                    {f.summary || '—'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
