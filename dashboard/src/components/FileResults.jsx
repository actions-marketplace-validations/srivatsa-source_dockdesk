export default function FileResults({ files }) {
  const riskStyle = {
    HIGH: 'text-white font-bold',
    MEDIUM: 'text-mono-dim',
    LOW: 'text-mono-dim opacity-60',
  }

  return (
    <div className="bg-mono-card border border-mono-border p-6 retro-card">
      <h3 className="text-sm font-bold text-white mb-4 tracking-widest">FILE RESULTS // LATEST RUN</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-xs font-mono">
          <thead>
            <tr className="border-b border-mono-border text-mono-dim uppercase tracking-wider">
              <th className="text-left py-2 pr-4">FILE</th>
              <th className="text-center py-2 px-2">STATUS</th>
              <th className="text-center py-2 px-2">RISK</th>
              <th className="text-center py-2 px-2">PUSH</th>
              <th className="text-right py-2 px-2">TIME</th>
              <th className="text-left py-2 pl-4">SUMMARY</th>
            </tr>
          </thead>
          <tbody>
            {files.map((f, i) => (
              <tr key={i} className="border-b border-mono-border/50 hover:bg-white/5 transition">
                <td className="py-2 pr-4">
                  <span className="text-white">
                    {f.file.length > 35 ? '...' + f.file.slice(-32) : f.file}
                  </span>
                </td>
                <td className="text-center py-2 px-2 text-white">
                  {f.status === 'PASS' ? 'PASS' : f.status === 'FAIL' ? 'FAIL' : f.status || '?'}
                </td>
                <td className="text-center py-2 px-2">
                  <span className={riskStyle[f.risk] || 'text-mono-dim'}>
                    {f.risk}
                  </span>
                </td>
                <td className="text-center py-2 px-2 text-white">
                  {f.safe_to_push ? '[Y]' : '[N]'}
                </td>
                <td className="text-right py-2 px-2 text-mono-dim">
                  {(f.duration_ms / 1000).toFixed(1)}s
                </td>
                <td className="py-2 pl-4">
                  <span className="text-mono-dim line-clamp-1">
                    {f.summary || '---'}
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
