export default function PushSafety({ files }) {
  const safe = files.filter(f => f.safe_to_push === true).length
  const unsafe = files.filter(f => f.safe_to_push === false).length
  const total = files.length || 1
  const safePercent = Math.round((safe / total) * 100)

  return (
    <div className="bg-mono-card border border-mono-border p-6 retro-card">
      <h3 className="text-sm font-bold text-white mb-4 tracking-widest">PUSH SAFETY</h3>
      
      {/* Gauge */}
      <div className="flex items-center justify-center mb-6">
        <div className="relative w-36 h-36">
          <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
            <circle cx="50" cy="50" r="40" fill="none" stroke="#222" strokeWidth="6" />
            <circle
              cx="50" cy="50" r="40" fill="none"
              stroke={safePercent >= 80 ? '#fff' : safePercent >= 50 ? '#888' : '#444'}
              strokeWidth="6"
              strokeDasharray={`${safePercent * 2.51} 251`}
              strokeLinecap="butt"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center font-mono">
            <span className="text-3xl font-bold text-white">{safePercent}%</span>
            <span className="text-xs text-mono-dim">SAFE</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 text-center font-mono">
        <div className="border border-mono-border p-3">
          <div className="text-xs text-mono-dim mb-1">[Y] SAFE</div>
          <div className="text-2xl font-bold text-white">{safe}</div>
        </div>
        <div className="border border-mono-border p-3">
          <div className="text-xs text-mono-dim mb-1">[N] UNSAFE</div>
          <div className="text-2xl font-bold text-mono-dim">{unsafe}</div>
        </div>
      </div>
    </div>
  )
}
