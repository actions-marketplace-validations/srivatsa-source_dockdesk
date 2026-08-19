import { useMemo, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, Layers3, Info, ArrowRightLeft, ChevronDown, FolderOpen, Folder, FileCode, FileText, File, Settings2, Package } from 'lucide-react'

const KIND_LABELS = {
  workspace: 'Workspace',
  directory: 'Directory',
  source: 'Source',
  doc: 'Docs',
  config: 'Config',
  asset: 'Asset',
}

const KIND_COLORS = {
  workspace: { fill: '#d4d4d8', stroke: '#fafafa', glow: 'rgba(255,255,255,0.2)', bg: 'rgba(255,255,255,0.08)' },
  directory: { fill: '#525252', stroke: '#a3a3a3', glow: 'rgba(255,255,255,0.08)', bg: 'rgba(255,255,255,0.04)' },
  source: { fill: '#737373', stroke: '#f5f5f5', glow: 'rgba(255,255,255,0.12)', bg: 'rgba(255,255,255,0.06)' },
  doc: { fill: '#a3a3a3', stroke: '#fafafa', glow: 'rgba(255,255,255,0.12)', bg: 'rgba(255,255,255,0.06)' },
  config: { fill: '#d4d4d8', stroke: '#fafafa', glow: 'rgba(255,255,255,0.12)', bg: 'rgba(255,255,255,0.06)' },
  asset: { fill: '#404040', stroke: '#737373', glow: 'rgba(255,255,255,0.06)', bg: 'rgba(255,255,255,0.03)' },
}

const LANG_COLORS = {
  python: '#3B82F6',
  javascript: '#EAB308',
  typescript: '#2563EB',
  java: '#EF4444',
  go: '#06B6D4',
  rust: '#F97316',
  dotnet: '#8B5CF6',
  markdown: '#6B7280',
  documentation: '#6B7280',
  config: '#A3A3A3',
}

function normalize(node) {
  return {
    ...node,
    kind: node.kind || 'asset',
    label: node.label || node.path || node.id,
    path: node.path || '',
    degree: node.degree || 0,
    incoming: node.incoming || 0,
    outgoing: node.outgoing || 0,
  }
}

function getFileIcon(kind) {
  if (kind === 'workspace') return Package
  if (kind === 'directory') return Folder
  if (kind === 'source') return FileCode
  if (kind === 'doc') return FileText
  if (kind === 'config') return Settings2
  return File
}

// Build a hierarchical tree from flat node list + edges
function buildTree(nodes, edges) {
  const nodeMap = new Map()
  nodes.forEach(n => nodeMap.set(n.id, { ...n, children: [] }))

  const containsEdges = edges.filter(e => e.kind === 'contains')
  const rootIds = new Set(nodes.map(n => n.id))

  containsEdges.forEach(edge => {
    const parent = nodeMap.get(edge.source)
    const child = nodeMap.get(edge.target)
    if (parent && child) {
      parent.children.push(child)
      rootIds.delete(edge.target)
    }
  })

  const sortChildren = (node) => {
    node.children.sort((a, b) => {
      if (a.kind === 'directory' && b.kind !== 'directory') return -1
      if (a.kind !== 'directory' && b.kind === 'directory') return 1
      return a.label.localeCompare(b.label)
    })
    node.children.forEach(sortChildren)
  }

  const roots = []
  rootIds.forEach(id => {
    const node = nodeMap.get(id)
    if (node) {
      sortChildren(node)
      roots.push(node)
    }
  })

  return roots
}

function filterTree(node, query) {
  if (!query) return { ...node }
  const matches = `${node.label} ${node.path} ${node.kind} ${node.language || ''}`.toLowerCase().includes(query.toLowerCase())
  const filteredChildren = node.children
    .map(child => filterTree(child, query))
    .filter(Boolean)

  if (matches || filteredChildren.length > 0) {
    return { ...node, children: filteredChildren }
  }
  return null
}

function countDescendants(node) {
  let count = 0
  node.children.forEach(child => {
    count += 1 + countDescendants(child)
  })
  return count
}

function TreeNode({ node, depth, selectedId, onSelect, expanded, onToggle, query }) {
  const isExpanded = expanded.has(node.id)
  const isSelected = selectedId === node.id
  const isDir = node.kind === 'directory' || node.kind === 'workspace'
  const hasChildren = node.children.length > 0
  const Icon = isDir && isExpanded ? FolderOpen : getFileIcon(node.kind)
  const langColor = LANG_COLORS[node.language] || '#6B7280'
  const descendantCount = isDir ? countDescendants(node) : 0

  return (
    <div>
      <button
        onClick={() => {
          onSelect(node.id)
          if (isDir && hasChildren) onToggle(node.id)
        }}
        className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-all group ${
          isSelected
            ? 'bg-white/10 border border-white/15'
            : 'hover:bg-white/5 border border-transparent'
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        <span className="w-4 h-4 flex items-center justify-center flex-shrink-0">
          {isDir && hasChildren ? (
            <motion.div
              animate={{ rotate: isExpanded ? 0 : -90 }}
              transition={{ duration: 0.15 }}
            >
              <ChevronDown size={13} className="text-white/50" />
            </motion.div>
          ) : (
            <span className="w-3" />
          )}
        </span>

        <Icon
          size={15}
          className="flex-shrink-0"
          style={{ color: isDir ? '#A3A3A3' : langColor }}
        />

        <span className={`text-[13px] truncate flex-1 ${isSelected ? 'text-white font-medium' : 'text-white/80'}`}>
          {node.label}
        </span>

        <span className="flex items-center gap-1.5 flex-shrink-0">
          {node.language && !isDir && (
            <span
              className="text-[9px] px-1.5 py-0.5 rounded-full font-mono uppercase tracking-wider"
              style={{ background: `${langColor}20`, color: langColor }}
            >
              {node.language}
            </span>
          )}
          {isDir && descendantCount > 0 && (
            <span className="text-[10px] text-white/30 font-mono">
              {descendantCount}
            </span>
          )}
          {!isDir && node.degree > 0 && (
            <span className="text-[10px] text-white/30 font-mono">
              {'\u2194'}{node.degree}
            </span>
          )}
        </span>
      </button>

      <AnimatePresence initial={false}>
        {isDir && isExpanded && hasChildren && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            style={{ overflow: 'hidden' }}
          >
            <div className="relative">
              <div
                className="absolute top-0 bottom-0 w-px bg-white/[0.08]"
                style={{ left: `${depth * 16 + 20}px` }}
              />
              {node.children.map(child => (
                <TreeNode
                  key={child.id}
                  node={child}
                  depth={depth + 1}
                  selectedId={selectedId}
                  onSelect={onSelect}
                  expanded={expanded}
                  onToggle={onToggle}
                  query={query}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function ConnectionGraph({ selectedNode, edges, allNodes }) {
  if (!selectedNode) return null

  const connectedEdges = edges.filter(
    e => e.source === selectedNode.id || e.target === selectedNode.id
  )

  if (connectedEdges.length === 0) {
    return (
      <div className="text-xs text-muted text-center py-4">No direct connections</div>
    )
  }

  const connectedIds = new Set()
  connectedEdges.forEach(e => {
    if (e.source !== selectedNode.id) connectedIds.add(e.source)
    if (e.target !== selectedNode.id) connectedIds.add(e.target)
  })

  const connectedNodes = allNodes.filter(n => connectedIds.has(n.id))
  const width = 340
  const height = 200
  const cx = width / 2
  const cy = height / 2
  const radius = 72

  const positions = new Map()
  positions.set(selectedNode.id, { x: cx, y: cy })

  connectedNodes.forEach((node, i) => {
    const angle = (Math.PI * 2 * i) / connectedNodes.length - Math.PI / 2
    positions.set(node.id, {
      x: cx + Math.cos(angle) * radius,
      y: cy + Math.sin(angle) * radius,
    })
  })

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-[200px]">
      {connectedEdges.map((edge, i) => {
        const src = positions.get(edge.source)
        const tgt = positions.get(edge.target)
        if (!src || !tgt) return null
        const isImport = edge.kind === 'imports'
        return (
          <line
            key={`edge-${i}`}
            x1={src.x} y1={src.y}
            x2={tgt.x} y2={tgt.y}
            stroke={isImport ? 'rgba(255,255,255,0.5)' : 'rgba(255,255,255,0.2)'}
            strokeWidth={isImport ? 1.5 : 1}
            strokeDasharray={isImport ? '4 3' : '0'}
          />
        )
      })}

      {connectedNodes.map(node => {
        const pos = positions.get(node.id)
        if (!pos) return null
        const style = KIND_COLORS[node.kind] || KIND_COLORS.asset
        return (
          <g key={node.id}>
            <circle cx={pos.x} cy={pos.y} r={6} fill={style.fill} stroke={style.stroke} strokeWidth={1} opacity={0.8} />
            <text x={pos.x} y={pos.y + 16} textAnchor="middle" fontSize="8" fill="rgba(255,255,255,0.6)">
              {node.label.length > 16 ? node.label.slice(0, 14) + '\u2026' : node.label}
            </text>
          </g>
        )
      })}

      <circle cx={cx} cy={cy} r={10} fill="rgba(255,255,255,0.15)" stroke="rgba(255,255,255,0.6)" strokeWidth={2} />
      <text x={cx} y={cy + 22} textAnchor="middle" fontSize="9" fill="rgba(255,255,255,0.9)" fontWeight="600">
        {selectedNode.label.length > 20 ? selectedNode.label.slice(0, 18) + '\u2026' : selectedNode.label}
      </text>
    </svg>
  )
}

export default function KnowledgeGraph({ graph }) {
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState(null)
  const [expandedState, setExpandedState] = useState(new Set())

  const nodes = useMemo(() => (graph?.nodes || []).map(normalize), [graph])
  const edges = graph?.edges || []
  const stats = graph?.stats || {}

  const tree = useMemo(() => buildTree(nodes, edges), [nodes, edges])

  // Auto-expand workspace root on first load
  useMemo(() => {
    if (expandedState.size === 0 && tree.length > 0) {
      const initial = new Set()
      tree.forEach(root => initial.add(root.id))
      setExpandedState(initial)
    }
  }, [tree]) // eslint-disable-line react-hooks/exhaustive-deps

  const toggleExpand = useCallback((nodeId) => {
    setExpandedState(prev => {
      const next = new Set(prev)
      if (next.has(nodeId)) next.delete(nodeId)
      else next.add(nodeId)
      return next
    })
  }, [])

  const filteredTree = useMemo(() => {
    if (!query.trim()) return tree
    return tree.map(root => filterTree(root, query.trim())).filter(Boolean)
  }, [tree, query])

  // Auto-expand all when searching
  const effectiveExpanded = useMemo(() => {
    if (!query.trim()) return expandedState
    const allIds = new Set()
    const collect = (node) => {
      allIds.add(node.id)
      node.children.forEach(collect)
    }
    filteredTree.forEach(collect)
    return allIds
  }, [query, filteredTree, expandedState])

  const selectedNode = nodes.find(n => n.id === selectedId) || null

  const selectedEdges = useMemo(() => {
    if (!selectedNode) return []
    return edges.filter(e => e.source === selectedNode.id || e.target === selectedNode.id)
  }, [selectedNode, edges])

  const importEdges = selectedEdges.filter(e => e.kind === 'imports')
  const containsEdges = selectedEdges.filter(e => e.kind === 'contains')

  const expandAll = useCallback(() => {
    const allIds = new Set()
    const collect = (node) => {
      if (node.kind === 'directory' || node.kind === 'workspace') allIds.add(node.id)
      node.children.forEach(collect)
    }
    tree.forEach(collect)
    setExpandedState(allIds)
  }, [tree])

  const collapseAll = useCallback(() => {
    const rootIds = new Set()
    tree.forEach(root => rootIds.add(root.id))
    setExpandedState(rootIds)
  }, [tree])

  if (!graph || nodes.length === 0) {
    return (
      <div className="glass-card rounded-2xl p-6 border border-white/10">
        <div className="flex items-center space-x-3 mb-3">
          <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center">
            <Layers3 size={18} className="text-white/70" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-white">Knowledge Graph</h2>
            <p className="text-xs text-muted">Generate a graph export to explore repository structure here.</p>
          </div>
        </div>
        <p className="text-sm text-muted">No graph data is available yet. Run an audit or export the graph with <span className="font-mono text-white">dockdesk knowledge-graph</span>.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="glass-card rounded-2xl p-5 border border-white/10">
        {/* Header */}
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between mb-4">
          <div>
            <div className="flex items-center space-x-3 mb-2">
              <div className="w-11 h-11 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center">
                <Layers3 size={19} className="text-white" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white">Knowledge Graph</h2>
                <p className="text-sm text-muted">Explore repository structure, files, and import relationships.</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2 text-[11px] text-muted">
              <span className="px-2 py-1 rounded-full bg-white/5 border border-white/10">{stats.total_nodes || 0} nodes</span>
              <span className="px-2 py-1 rounded-full bg-white/5 border border-white/10">{stats.total_edges || 0} edges</span>
              <span className="px-2 py-1 rounded-full bg-white/5 border border-white/10">{stats.source_nodes || 0} source</span>
              <span className="px-2 py-1 rounded-full bg-white/5 border border-white/10">{stats.doc_nodes || 0} docs</span>
              <span className="px-2 py-1 rounded-full bg-white/5 border border-white/10">{(stats.entry_points || []).length} entry pts</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <label className="relative block w-full lg:w-72">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search files and folders\u2026"
                className="w-full rounded-xl bg-black/20 border border-white/10 pl-9 pr-3 py-2 text-sm text-white placeholder:text-muted outline-none focus:border-white/20"
              />
            </label>
            <button
              onClick={expandAll}
              className="text-[11px] text-muted hover:text-white px-2.5 py-2 rounded-lg bg-white/5 border border-white/10 hover:bg-white/[0.08] transition whitespace-nowrap"
            >
              Expand all
            </button>
            <button
              onClick={collapseAll}
              className="text-[11px] text-muted hover:text-white px-2.5 py-2 rounded-lg bg-white/5 border border-white/10 hover:bg-white/[0.08] transition whitespace-nowrap"
            >
              Collapse
            </button>
          </div>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap gap-2 mb-4">
          {Object.entries(KIND_LABELS).map(([kind, label]) => (
            <span key={kind} className="inline-flex items-center space-x-2 px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-[11px] text-muted">
              <span className="w-2 h-2 rounded-full" style={{ background: KIND_COLORS[kind]?.fill || '#999' }} />
              <span>{label}</span>
            </span>
          ))}
        </div>

        {/* Main content grid */}
        <div className="grid grid-cols-1 xl:grid-cols-[1.6fr_0.9fr] gap-5">
          {/* Tree explorer */}
          <div className="rounded-2xl border border-white/10 bg-black/20 overflow-hidden">
            <div className="max-h-[600px] overflow-y-auto p-2">
              {filteredTree.length === 0 ? (
                <div className="text-sm text-muted text-center py-8">
                  {query ? 'No files match your search.' : 'No nodes to display.'}
                </div>
              ) : (
                filteredTree.map(root => (
                  <TreeNode
                    key={root.id}
                    node={root}
                    depth={0}
                    selectedId={selectedId}
                    onSelect={setSelectedId}
                    expanded={effectiveExpanded}
                    onToggle={toggleExpand}
                    query={query}
                  />
                ))
              )}
            </div>
          </div>

          {/* Details panel */}
          <div className="space-y-4">
            <div className="glass-card rounded-2xl p-4 border border-white/10">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-2 text-white">
                  <Info size={15} />
                  <span className="text-sm font-semibold">Node Details</span>
                </div>
                <span className="text-[11px] text-muted">{KIND_LABELS[selectedNode?.kind] || 'Select a node'}</span>
              </div>

              {selectedNode ? (
                <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} key={selectedNode.id} className="space-y-3">
                  <div>
                    <p className="text-base font-semibold text-white break-words">{selectedNode.label}</p>
                    <p className="text-xs text-muted font-mono break-words">{selectedNode.path || selectedNode.id}</p>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="rounded-xl bg-white/5 border border-white/10 p-3">
                      <div className="text-muted">Kind</div>
                      <div className="text-white font-medium">{KIND_LABELS[selectedNode.kind] || selectedNode.kind}</div>
                    </div>
                    <div className="rounded-xl bg-white/5 border border-white/10 p-3">
                      <div className="text-muted">Language</div>
                      <div className="text-white font-medium flex items-center gap-1.5">
                        {selectedNode.language && (
                          <span className="w-2 h-2 rounded-full" style={{ background: LANG_COLORS[selectedNode.language] || '#6B7280' }} />
                        )}
                        {selectedNode.language || '\u2014'}
                      </div>
                    </div>
                    <div className="rounded-xl bg-white/5 border border-white/10 p-3">
                      <div className="text-muted">Incoming</div>
                      <div className="text-white font-medium">{selectedNode.incoming}</div>
                    </div>
                    <div className="rounded-xl bg-white/5 border border-white/10 p-3">
                      <div className="text-muted">Outgoing</div>
                      <div className="text-white font-medium">{selectedNode.outgoing}</div>
                    </div>
                  </div>

                  {selectedNode.size > 0 && (
                    <div className="text-xs text-muted">
                      Size: <span className="text-white">{selectedNode.size > 1024 ? `${(selectedNode.size / 1024).toFixed(1)} KB` : `${selectedNode.size} B`}</span>
                    </div>
                  )}

                  <div className="flex items-center space-x-2 text-[11px] text-muted">
                    <ArrowRightLeft size={12} />
                    <span>{importEdges.length} import(s) {'\u00B7'} {containsEdges.length} containment</span>
                  </div>
                </motion.div>
              ) : (
                <p className="text-sm text-muted">Click a file or folder to inspect its context.</p>
              )}
            </div>

            {/* Mini connection graph */}
            <div className="glass-card rounded-2xl p-4 border border-white/10">
              <div className="flex items-center space-x-2 mb-3 text-white">
                <ArrowRightLeft size={15} />
                <span className="text-sm font-semibold">Connections</span>
              </div>
              <div className="rounded-xl bg-black/20 border border-white/10 overflow-hidden">
                {selectedNode ? (
                  <ConnectionGraph selectedNode={selectedNode} edges={edges} allNodes={nodes} />
                ) : (
                  <div className="text-xs text-muted text-center py-8">Select a node to view its connections</div>
                )}
              </div>
            </div>

            {/* Entry points */}
            {(stats.entry_points || []).length > 0 && (
              <div className="glass-card rounded-2xl p-4 border border-white/10">
                <div className="text-[11px] uppercase tracking-widest text-muted mb-2">Entry points</div>
                <div className="space-y-1 max-h-32 overflow-auto pr-1">
                  {stats.entry_points.slice(0, 10).map((entry) => (
                    <button
                      key={entry}
                      onClick={() => {
                        const matchNode = nodes.find(n => n.path === entry)
                        if (matchNode) setSelectedId(matchNode.id)
                      }}
                      className="block w-full text-left text-xs text-white/85 font-mono rounded-lg bg-white/5 border border-white/10 px-2 py-1 break-words hover:bg-white/[0.08] transition"
                    >
                      {entry}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}