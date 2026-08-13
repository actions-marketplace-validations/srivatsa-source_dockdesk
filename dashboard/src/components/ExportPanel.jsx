import { useState } from 'react'
import { motion } from 'framer-motion'
import { Download, FileSpreadsheet, Table2, BarChart3 } from 'lucide-react'

async function exportToExcel(data) {
  const XLSX = await import('xlsx')
  const wb = XLSX.utils.book_new()

  const summaryRows = [
    ['DockDesk Audit Report', '', new Date().toLocaleDateString()], [],
    ['Metric', 'Value'],
    ['Total Audits', data.stats?.total_audits ?? 0],
    ['Files Analyzed', data.stats?.total_files_audited ?? 0],
    ['Fixes Applied', data.stats?.total_fixes_applied ?? 0],
    ['Avg Duration (s)', (data.stats?.average_duration_seconds ?? 0).toFixed(1)], [],
    ['Risk Distribution'],
    ['HIGH', data.stats?.risk_totals?.HIGH ?? 0],
    ['MEDIUM', data.stats?.risk_totals?.MEDIUM ?? 0],
    ['LOW', data.stats?.risk_totals?.LOW ?? 0], [],
    ['Models Used'],
    ['Code Model', data.dual_model?.code_model ?? ''],
    ['Reasoning Model', data.dual_model?.reasoning_model ?? ''],
  ]
  if (data.stats?.model_usage) {
    summaryRows.push([], ['Model Usage Breakdown'])
    for (const [model, count] of Object.entries(data.stats.model_usage)) summaryRows.push([model, count])
  }
  const summarySheet = XLSX.utils.aoa_to_sheet(summaryRows)
  summarySheet['!cols'] = [{ wch: 30 }, { wch: 25 }, { wch: 20 }]
  XLSX.utils.book_append_sheet(wb, summarySheet, 'Summary')

  const fileHeaders = ['File', 'Status', 'Risk', 'Safe to Push', 'Summary', 'Code Model', 'Reasoning Model', 'Duration (s)']
  const fileRows = (data.latest_run_files || []).map(f => [f.file, f.status, f.risk, f.safe_to_push ? 'YES' : 'NO', f.summary || '', f.code_model || '', f.reasoning_model || '', (f.duration_ms / 1000).toFixed(1)])
  const fileSheet = XLSX.utils.aoa_to_sheet([fileHeaders, ...fileRows])
  fileSheet['!cols'] = [{ wch: 40 }, { wch: 10 }, { wch: 10 }, { wch: 12 }, { wch: 60 }, { wch: 22 }, { wch: 22 }, { wch: 12 }]
  XLSX.utils.book_append_sheet(wb, fileSheet, 'File Results')

  const timeHeaders = ['Date', 'Pass', 'Fail', 'Skip', 'Fixes', 'Model', 'Duration (s)']
  const timeRows = (data.timeline || []).map(t => [t.date, t.pass, t.fail, t.skip, t.fixes, t.model || '', (t.duration ?? 0).toFixed(1)])
  const timeSheet = XLSX.utils.aoa_to_sheet([timeHeaders, ...timeRows])
  XLSX.utils.book_append_sheet(wb, timeSheet, 'Timeline')

  const runHeaders = ['Run ID', 'Timestamp', 'Branch', 'Commit', 'Model', 'Files Discovered', 'Files Audited', 'Pass', 'Fail', 'HIGH', 'MEDIUM', 'LOW', 'Duration (s)']
  const runRows = (data.recent_runs || []).map(r => [r.run_id || '', r.timestamp || '', r.git_branch || '', r.git_commit || '', r.model || '', r.files_discovered ?? 0, r.files_audited ?? 0, r.pass_count ?? 0, r.fail_count ?? 0, r.risk_distribution?.HIGH ?? 0, r.risk_distribution?.MEDIUM ?? 0, r.risk_distribution?.LOW ?? 0, (r.duration_seconds ?? 0).toFixed(1)])
  const runSheet = XLSX.utils.aoa_to_sheet([runHeaders, ...runRows])
  XLSX.utils.book_append_sheet(wb, runSheet, 'Recent Runs')

  const dateStr = new Date().toISOString().slice(0, 10)
  XLSX.writeFile(wb, `DockDesk_Audit_Report_${dateStr}.xlsx`)
}

function ExportCard({ icon: Icon, title, description, buttonText, onClick, gradient }) {
  return (
    <motion.div
      whileHover={{ scale: 1.02, y: -2 }}
      className="glass-card rounded-xl p-5 transition-all group"
    >
      <div className="flex items-start space-x-4">
        <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${gradient} flex items-center justify-center flex-shrink-0`}>
          <Icon size={22} className="text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-semibold text-white mb-1">{title}</h4>
          <p className="text-xs text-muted mb-3">{description}</p>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={onClick}
            className="inline-flex items-center space-x-1.5 text-xs font-medium text-white bg-gradient-to-r from-purple-600/50 to-pink-600/50 hover:from-purple-500/60 hover:to-pink-500/60 px-3 py-1.5 rounded-lg transition-colors"
          >
            <Download size={12} />
            <span>{buttonText}</span>
          </motion.button>
        </div>
      </div>
    </motion.div>
  )
}

export default function ExportPanel({ data }) {
  const [exporting, setExporting] = useState(false)

  const handleExcelExport = async () => {
    setExporting(true)
    try { await exportToExcel(data) } catch (err) { console.error('Excel export failed:', err) } finally { setExporting(false) }
  }
  const handlePDFExport = () => window.print()
  const handleCSVExport = () => {
    const files = data?.latest_run_files || []
    const header = 'File,Status,Risk,Safe to Push,Summary,Code Model,Duration (s)\n'
    const rows = files.map(f => `"${f.file}","${f.status}","${f.risk}","${f.safe_to_push ? 'YES' : 'NO'}","${(f.summary || '').replace(/"/g, '""')}","${f.code_model || ''}","${(f.duration_ms / 1000).toFixed(1)}"`).join('\n')
    const blob = new Blob([header + rows], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `DockDesk_FileResults_${new Date().toISOString().slice(0, 10)}.csv`; a.click()
    URL.revokeObjectURL(url)
  }

  const fileCount = data?.latest_run_files?.length || 0
  const runCount = data?.recent_runs?.length || 0

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card glass-card-hover rounded-xl p-6">
        <div className="flex items-center space-x-2 mb-1">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-purple-500/20 to-cyan-500/20 flex items-center justify-center">
            <BarChart3 size={14} className="text-cyan-400" />
          </div>
          <h3 className="text-sm font-semibold text-white">Export Reports</h3>
        </div>
        <p className="text-xs text-muted mb-5">Generate industry-standard reports. {fileCount} files across {runCount} runs available.</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <ExportCard icon={FileSpreadsheet} title="Excel Report" description="Multi-sheet workbook with Summary, File Results, Timeline, and Recent Runs." buttonText={exporting ? 'Generating...' : 'Export .xlsx'} onClick={handleExcelExport} gradient="from-emerald-600 to-emerald-500" />
          <ExportCard icon={Table2} title="CSV Export" description="Quick file results export as CSV. Import into any spreadsheet or BI tool." buttonText="Export .csv" onClick={handleCSVExport} gradient="from-cyan-600 to-cyan-500" />
          <ExportCard icon={Download} title="PDF Report" description="Print-optimized audit report. Uses browser print dialog (Ctrl+P)." buttonText="Print / Save PDF" onClick={handlePDFExport} gradient="from-purple-600 to-pink-600" />
        </div>
      </motion.div>

      {fileCount > 0 && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="glass-card glass-card-hover rounded-xl p-6">
          <h4 className="text-sm font-semibold text-white mb-3">Data Preview</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-purple-500/10 text-muted uppercase tracking-wider text-[10px]">
                  <th className="text-left py-2.5 pr-4">File</th>
                  <th className="text-center py-2.5 px-2">Status</th>
                  <th className="text-center py-2.5 px-2">Risk</th>
                  <th className="text-center py-2.5 px-2">Safe</th>
                  <th className="text-right py-2.5 px-2">Model</th>
                </tr>
              </thead>
              <tbody>
                {data.latest_run_files.slice(0, 10).map((f, i) => (
                  <motion.tr key={i} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.03 }} className="border-b border-purple-500/[0.06]">
                    <td className="py-2 pr-4 text-white font-mono">{f.file}</td>
                    <td className="text-center py-2 px-2">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${f.status === 'PASS' ? 'bg-cyan-500/15 text-cyan-400' : f.status === 'FAIL' ? 'bg-pink-500/15 text-pink-400' : 'bg-slate-500/15 text-slate-400'}`}>{f.status}</span>
                    </td>
                    <td className="text-center py-2 px-2">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${f.risk === 'HIGH' ? 'bg-pink-500/15 text-pink-400' : f.risk === 'MEDIUM' ? 'bg-yellow-500/15 text-yellow-400' : 'bg-cyan-500/15 text-cyan-400'}`}>{f.risk}</span>
                    </td>
                    <td className="text-center py-2 px-2">{f.safe_to_push ? '\u2705' : '\u274c'}</td>
                    <td className="text-right py-2 px-2 text-muted font-mono text-[10px]">{f.code_model || '\u2014'}</td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>
      )}
    </div>
  )
}
