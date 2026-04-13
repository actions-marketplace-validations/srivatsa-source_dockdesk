import { useState } from 'react'
import { Download, FileSpreadsheet, Table2, Clock, BarChart3 } from 'lucide-react'

// SheetJS dynamic import for Excel export
async function exportToExcel(data) {
  const XLSX = await import('xlsx')

  const wb = XLSX.utils.book_new()

  const headerStyle = {
    font: { bold: true, color: { rgb: 'FFFFFFFF' } },
    fill: { fgColor: { rgb: '1E40AF' } },
    alignment: { horizontal: 'center', vertical: 'center' },
  }
  const riskStyles = {
    HIGH: { fill: { fgColor: { rgb: 'FEE2E2' } }, font: { color: { rgb: 'B91C1C' }, bold: true } },
    MEDIUM: { fill: { fgColor: { rgb: 'FEF3C7' } }, font: { color: { rgb: 'B45309' }, bold: true } },
    LOW: { fill: { fgColor: { rgb: 'DCFCE7' } }, font: { color: { rgb: '15803D' }, bold: true } },
  }

  const applyHeaderStyle = (sheet, headers) => {
    for (let c = 0; c < headers.length; c++) {
      const cellRef = XLSX.utils.encode_cell({ r: 0, c })
      if (sheet[cellRef]) {
        sheet[cellRef].s = headerStyle
      }
    }
  }

  // ── Sheet 1: Summary ──
  const summaryRows = [
    ['DockDesk Audit Report', '', new Date().toLocaleDateString()],
    [],
    ['Metric', 'Value'],
    ['Total Audits', data.stats?.total_audits ?? 0],
    ['Files Analyzed', data.stats?.total_files_audited ?? 0],
    ['Fixes Applied', data.stats?.total_fixes_applied ?? 0],
    ['Avg Duration (s)', (data.stats?.average_duration_seconds ?? 0).toFixed(1)],
    [],
    ['Risk Distribution'],
    ['HIGH', data.stats?.risk_totals?.HIGH ?? 0],
    ['MEDIUM', data.stats?.risk_totals?.MEDIUM ?? 0],
    ['LOW', data.stats?.risk_totals?.LOW ?? 0],
    [],
    ['Models Used'],
    ['Code Model', data.dual_model?.code_model ?? ''],
    ['Reasoning Model', data.dual_model?.reasoning_model ?? ''],
  ]

  // Add model usage
  if (data.stats?.model_usage) {
    summaryRows.push([])
    summaryRows.push(['Model Usage Breakdown'])
    for (const [model, count] of Object.entries(data.stats.model_usage)) {
      summaryRows.push([model, count])
    }
  }

  const summarySheet = XLSX.utils.aoa_to_sheet(summaryRows)
  summarySheet['!cols'] = [{ wch: 30 }, { wch: 25 }, { wch: 20 }]
  XLSX.utils.book_append_sheet(wb, summarySheet, 'Summary')

  // ── Sheet 2: File Results ──
  const fileHeaders = ['File', 'Status', 'Risk', 'Safe to Push', 'Summary', 'Code Model', 'Reasoning Model', 'Duration (s)']
  const fileRows = (data.latest_run_files || []).map(f => [
    f.file,
    f.status,
    f.risk,
    f.safe_to_push ? 'YES' : 'NO',
    f.summary || '',
    f.code_model || '',
    f.reasoning_model || '',
    (f.duration_ms / 1000).toFixed(1),
  ])
  const fileSheet = XLSX.utils.aoa_to_sheet([fileHeaders, ...fileRows])
  fileSheet['!cols'] = [
    { wch: 40 }, { wch: 10 }, { wch: 10 }, { wch: 12 },
    { wch: 60 }, { wch: 22 }, { wch: 22 }, { wch: 12 },
  ]
  XLSX.utils.book_append_sheet(wb, fileSheet, 'File Results')
  applyHeaderStyle(fileSheet, fileHeaders)
  // Risk column is index 2 in File Results.
  for (let r = 1; r <= fileRows.length; r++) {
    const ref = XLSX.utils.encode_cell({ r, c: 2 })
    const cell = fileSheet[ref]
    if (!cell) continue
    const risk = String(cell.v || '').toUpperCase()
    if (riskStyles[risk]) {
      cell.s = { ...riskStyles[risk], alignment: { horizontal: 'center' } }
    }
  }

  // ── Sheet 3: Timeline ──
  const timeHeaders = ['Date', 'Pass', 'Fail', 'Skip', 'Fixes', 'Model', 'Duration (s)']
  const timeRows = (data.timeline || []).map(t => [
    t.date, t.pass, t.fail, t.skip, t.fixes, t.model || '', (t.duration ?? 0).toFixed(1),
  ])
  const timeSheet = XLSX.utils.aoa_to_sheet([timeHeaders, ...timeRows])
  timeSheet['!cols'] = [
    { wch: 14 }, { wch: 8 }, { wch: 8 }, { wch: 8 },
    { wch: 8 }, { wch: 22 }, { wch: 14 },
  ]
  XLSX.utils.book_append_sheet(wb, timeSheet, 'Timeline')
  applyHeaderStyle(timeSheet, timeHeaders)

  // ── Sheet 4: Recent Runs ──
  const runHeaders = [
    'Run ID', 'Timestamp', 'Branch', 'Commit', 'Model',
    'Files Discovered', 'Files Audited', 'Pass', 'Fail',
    'HIGH', 'MEDIUM', 'LOW', 'Duration (s)'
  ]
  const runRows = (data.recent_runs || []).map(r => [
    r.run_id || '',
    r.timestamp || '',
    r.git_branch || '',
    r.git_commit || '',
    r.model || '',
    r.files_discovered ?? 0,
    r.files_audited ?? 0,
    r.pass_count ?? 0,
    r.fail_count ?? 0,
    r.risk_distribution?.HIGH ?? 0,
    r.risk_distribution?.MEDIUM ?? 0,
    r.risk_distribution?.LOW ?? 0,
    (r.duration_seconds ?? 0).toFixed(1),
  ])
  const runSheet = XLSX.utils.aoa_to_sheet([runHeaders, ...runRows])
  runSheet['!cols'] = [
    { wch: 30 }, { wch: 22 }, { wch: 12 }, { wch: 12 },
    { wch: 22 }, { wch: 16 }, { wch: 14 }, { wch: 8 },
    { wch: 8 }, { wch: 8 }, { wch: 10 }, { wch: 8 }, { wch: 14 },
  ]
  XLSX.utils.book_append_sheet(wb, runSheet, 'Recent Runs')
  applyHeaderStyle(runSheet, runHeaders)

  // Download
  const dateStr = new Date().toISOString().slice(0, 10)
  XLSX.writeFile(wb, `DockDesk_Audit_Report_${dateStr}.xlsx`)
}

function ExportCard({ icon: Icon, title, description, buttonText, onClick, accent }) {
  return (
    <div className="bg-surface-700 border border-white/5 rounded-xl p-5 hover:border-white/10 transition-all group">
      <div className="flex items-start space-x-4">
        <div className={`w-11 h-11 rounded-xl ${accent} flex items-center justify-center flex-shrink-0`}>
          <Icon size={22} className="text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-semibold text-white mb-1">{title}</h4>
          <p className="text-xs text-muted mb-3">{description}</p>
          <button
            onClick={onClick}
            className="inline-flex items-center space-x-1.5 text-xs font-medium text-white bg-white/10 hover:bg-white/15 px-3 py-1.5 rounded-lg transition-colors"
          >
            <Download size={12} />
            <span>{buttonText}</span>
          </button>
        </div>
      </div>
    </div>
  )
}

export default function ExportPanel({ data }) {
  const [exporting, setExporting] = useState(false)

  const handleExcelExport = async () => {
    setExporting(true)
    try {
      await exportToExcel(data)
    } catch (err) {
      console.error('Excel export failed:', err)
    } finally {
      setExporting(false)
    }
  }

  const handlePDFExport = () => {
    window.print()
  }

  // CSV export for quick data access
  const handleCSVExport = () => {
    const files = data?.latest_run_files || []
    const header = 'File,Status,Risk,Safe to Push,Summary,Code Model,Duration (s)\n'
    const rows = files.map(f =>
      `"${f.file}","${f.status}","${f.risk}","${f.safe_to_push ? 'YES' : 'NO'}","${(f.summary || '').replace(/"/g, '""')}","${f.code_model || ''}","${(f.duration_ms / 1000).toFixed(1)}"`
    ).join('\n')

    const blob = new Blob([header + rows], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `DockDesk_FileResults_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const fileCount = data?.latest_run_files?.length || 0
  const runCount = data?.recent_runs?.length || 0

  return (
    <div className="space-y-6">
      {/* Header stats */}
      <div className="bg-surface-600 border border-white/5 rounded-xl p-6">
        <div className="flex items-center space-x-2 mb-1">
          <BarChart3 size={16} className="text-info" />
          <h3 className="text-sm font-semibold text-white">Export Reports</h3>
        </div>
        <p className="text-xs text-muted mb-5">
          Generate industry-standard reports from your audit data. {fileCount} files across {runCount} runs available.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <ExportCard
            icon={FileSpreadsheet}
            title="Excel Report"
            description="Multi-sheet workbook with Summary, File Results, Timeline, and Recent Runs. Industry-standard .xlsx format."
            buttonText={exporting ? 'Generating...' : 'Export .xlsx'}
            onClick={handleExcelExport}
            accent="bg-emerald-600"
          />
          <ExportCard
            icon={Table2}
            title="CSV Export"
            description="Quick file results export as comma-separated values. Import into any spreadsheet or BI tool."
            buttonText="Export .csv"
            onClick={handleCSVExport}
            accent="bg-info"
          />
          <ExportCard
            icon={Download}
            title="PDF Report"
            description="Print-optimized audit report with all dashboard sections. Uses browser print dialog (Ctrl+P)."
            buttonText="Print / Save PDF"
            onClick={handlePDFExport}
            accent="bg-accent"
          />
        </div>
      </div>

      {/* Preview table */}
      {fileCount > 0 && (
        <div className="bg-surface-600 border border-white/5 rounded-xl p-6">
          <h4 className="text-sm font-semibold text-white mb-3">Data Preview</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-white/5 text-muted uppercase tracking-wider text-[10px]">
                  <th className="text-left py-2.5 pr-4">File</th>
                  <th className="text-center py-2.5 px-2">Status</th>
                  <th className="text-center py-2.5 px-2">Risk</th>
                  <th className="text-center py-2.5 px-2">Safe</th>
                  <th className="text-right py-2.5 px-2">Model</th>
                </tr>
              </thead>
              <tbody>
                {data.latest_run_files.slice(0, 10).map((f, i) => (
                  <tr key={i} className="border-b border-white/[0.03]">
                    <td className="py-2 pr-4 text-white font-mono">{f.file}</td>
                    <td className="text-center py-2 px-2">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                        f.status === 'PASS' ? 'bg-emerald-500/15 text-emerald-400' :
                        f.status === 'FAIL' ? 'bg-red-500/15 text-red-400' :
                        'bg-slate-500/15 text-slate-400'
                      }`}>{f.status}</span>
                    </td>
                    <td className="text-center py-2 px-2">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                        f.risk === 'HIGH' ? 'bg-red-500/15 text-red-400' :
                        f.risk === 'MEDIUM' ? 'bg-amber-500/15 text-amber-400' :
                        'bg-emerald-500/15 text-emerald-400'
                      }`}>{f.risk}</span>
                    </td>
                    <td className="text-center py-2 px-2">
                      {f.safe_to_push ? '✅' : '❌'}
                    </td>
                    <td className="text-right py-2 px-2 text-muted font-mono text-[10px]">
                      {f.code_model || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
