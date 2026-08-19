import { BarChart3, FileSearch, Activity, Shield, Cpu, Clock, ChevronLeft, ChevronRight, GitBranch, FileSpreadsheet, MessageCircle, AlertTriangle, Users, Link2, Workflow, Network, Settings } from 'lucide-react'

const NAV_SECTIONS = [
  {
    label: 'Analysis',
    items: [
      { id: 'overview', icon: BarChart3, label: 'Overview' },
      { id: 'tree', icon: GitBranch, label: 'Audit Tree' },
      { id: 'knowledge-graph', icon: Network, label: 'Knowledge Graph' },
      { id: 'files', icon: FileSearch, label: 'File Results' },
      { id: 'safety', icon: Shield, label: 'Push Safety' },
    ],
  },
  {
    label: 'Tracking',
    items: [
      { id: 'accountability', icon: Users, label: 'Accountability' },
      { id: 'audit-trail', icon: Link2, label: 'Audit Trail' },
      { id: 'pipeline', icon: Workflow, label: 'CI/CD Pipeline' },
      { id: 'timeline', icon: Activity, label: 'Timeline' },
      { id: 'anomalies', icon: AlertTriangle, label: 'Anomalies' },
    ],
  },
  {
    label: 'Integrations',
    items: [
      { id: 'models', icon: Cpu, label: 'Models' },
      { id: 'runs', icon: Clock, label: 'Recent Runs' },
      { id: 'reports', icon: FileSpreadsheet, label: 'Reports' },
      { id: 'discord', icon: MessageCircle, label: 'Discord' },
      { id: 'settings', icon: Settings, label: 'Settings' },
    ],
  },
]

export default function Sidebar({ activeView, onNavigate, collapsed, onToggle }) {
  return (
    <aside
      className={`fixed left-0 top-0 h-full bg-surface-700 border-r border-accent/10 flex flex-col z-30 transition-all duration-300 ${
        collapsed ? 'w-16' : 'w-56'
      }`}
    >
      {/* Logo */}
      <div className="flex items-center h-14 px-4 border-b border-accent/10">
        <div className="flex items-center space-x-2.5 overflow-hidden">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-pink flex items-center justify-center flex-shrink-0 glow-breathe">
            <Shield size={16} className="text-white" />
          </div>
          {!collapsed && (
            <span className="font-bold text-white text-sm tracking-wide whitespace-nowrap bg-gradient-to-r from-accent-light to-pink-light bg-clip-text text-transparent">
              DockDesk
            </span>
          )}
        </div>
      </div>

      {/* Navigation with category groups */}
      <nav className="flex-1 py-3 overflow-y-auto">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label}>
            {!collapsed && (
              <div className="px-4 pt-3 pb-1.5">
                <span className="text-[10px] font-semibold uppercase tracking-widest text-accent/50">
                  {section.label}
                </span>
              </div>
            )}
            <div className="space-y-0.5 px-2">
              {section.items.map((item) => {
                const Icon = item.icon
                const isActive = activeView === item.id
                return (
                  <button
                    key={item.id}
                    onClick={() => onNavigate(item.id)}
                    className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-sm transition-all ${
                      isActive
                        ? 'sidebar-active text-accent-light font-medium'
                        : 'text-muted hover:text-white hover:bg-accent/5'
                    }`}
                    title={collapsed ? item.label : undefined}
                  >
                    <Icon size={17} className={`flex-shrink-0 ${isActive ? 'text-accent-light' : ''}`} />
                    {!collapsed && <span>{item.label}</span>}
                  </button>
                )
              })}
            </div>
            {!collapsed && <div className="mx-4 my-2 border-t border-accent/5" />}
          </div>
        ))}
      </nav>

      {/* Version + collapse */}
      <div className="p-2 border-t border-accent/10 space-y-1">
        {!collapsed && (
          <div className="text-center text-[10px] text-accent/40 font-mono pb-1">v3.0.0 - Neural</div>
        )}
        <button
          onClick={onToggle}
          className="w-full flex items-center justify-center py-2 rounded-lg text-muted hover:text-accent-light hover:bg-accent/5 transition"
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
    </aside>
  )
}
