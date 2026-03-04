import { ShieldCheck, ShieldAlert } from 'lucide-react'

export default function PushSafety({ files }) {
  const safe = files.filter(f => f.safe_to_push === true).length
  const unsafe = files.filter(f => f.safe_to_push === false).length
  const total = files.length || 1
  const safePercent = Math.round((safe / total) * 100)

  const ringColor = safePercent >= 80 ? '#10b981' : safePercent >= 50 ? '#f59e0b' : '#ef4444'
  const StatusIcon = safePercent >= 80 ? ShieldCheck : ShieldAlert

  return (
    <div className="bg-surface-600 border border-white/5 rounded-xl p-6">
      <h3 className="text-sm font-semibold text-white mb-4">Push Safety</h3>

      {/* Gauge */}
      <div className="flex items-center justify-center mb-5">
        <div className="relative w-36 h-36">
          <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
            <circle cx="50" cy="50" r="40" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="7" />
            <circle
              cx="50" cy="50" r="40" fill="none"
              stroke={ringColor}
              strokeWidth="7"
              strokeDasharray={`${safePercent * 2.51} 251`}
              strokeLinecap="round"
              className="transition-all duration-700"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <StatusIcon size={20} style={{ color: ringColor }} className="mb-1" />
            <span className="text-2xl font-bold text-white">{safePercent}%</span>
            <span className="text-[10px] text-muted uppercase tracking-wider">safe</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="bg-success-muted rounded-lg p-3 text-center">
          <p className="text-xs text-success font-medium mb-0.5">Safe</p>
          <p className="text-xl font-bold text-white">{safe}</p>
        </div>
        <div className="bg-danger-muted rounded-lg p-3 text-center">
          <p className="text-xs text-danger font-medium mb-0.5">Unsafe</p>
          <p className="text-xl font-bold text-white">{unsafe}</p>
        </div>
      </div>
    </div>
  )
}
