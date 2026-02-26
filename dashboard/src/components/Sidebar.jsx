import { BarChart3, FileSearch, Activity, Shield, Cpu, Clock, ChevronLeft, ChevronRight } from 'lucide-react'

const NAV_ITEMS = [
  { id: 'overview', icon: BarChart3, label: 'Overview' },
  { id: 'files', icon: FileSearch, label: 'File Results' },
  { id: 'timeline', icon: Activity, label: 'Timeline' },
  { id: 'safety', icon: Shield, label: 'Push Safety' },
  { id: 'models', icon: Cpu, label: 'Models' },
  { id: 'runs', icon: Clock, label: 'Recent Runs' },
]

export default function Sidebar({ activeView, onNavigate, collapsed, onToggle }) {
  return (
    <aside
      className={`fixed left-0 top-0 h-full bg-surface-700 border-r border-white/5 flex flex-col z-30 transition-all duration-300 ${
        collapsed ? 'w-16' : 'w-56'
      }`}
    >
      {/* Logo */}
      <div className="flex items-center h-14 px-4 border-b border-white/5">
        <div className="flex items-center space-x-2 overflow-hidden">
          <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center flex-shrink-0">
            <Shield size={18} className="text-white" />
          </div>
          {!collapsed && (
            <span className="font-semibold text-white text-sm tracking-wide whitespace-nowrap">
              DockDesk
            </span>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-3 space-y-0.5 px-2">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon
          const isActive = activeView === item.id
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm transition-all ${
                isActive
                  ? 'bg-accent/15 text-accent-light border-l-2 border-accent'
                  : 'text-muted hover:text-white hover:bg-white/5'
              }`}
              title={collapsed ? item.label : undefined}
            >
              <Icon size={18} className="flex-shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </button>
          )
        })}
      </nav>

      {/* Collapse toggle */}
      <div className="p-2 border-t border-white/5">
        <button
          onClick={onToggle}
          className="w-full flex items-center justify-center py-2 rounded-lg text-muted hover:text-white hover:bg-white/5 transition"
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
    </aside>
  )
}
