import { useState, useMemo, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Settings, Cpu, Zap, Save, Check, AlertTriangle, RotateCcw, Plus, X, ChevronDown, Download, Loader2 } from 'lucide-react'

const AUDIT_MODELS = {
  'qwen2.5-coder:1.5b': { tier: 'SMALL', params: '1.5B', desc: 'Ultra-fast, minimal resource usage.', role: 'Code' },
  'deepseek-r1:1.5b': { tier: 'SMALL', params: '1.5B', desc: 'DeepSeek R1 reasoning model.', role: 'Reasoning' },
  'deepseek-coder:1.3b': { tier: 'SMALL', params: '1.3B', desc: 'Compact coder with strong reasoning.', role: 'Code' },
  'gemma:2b': { tier: 'SMALL', params: '2B', desc: "Google's lightweight Gemma model.", role: 'Code' },
  'qwen2.5-coder:3b': { tier: 'SMALL', params: '3B', desc: 'Fast, efficient coder model.', role: 'Code' },
  'starcoder2:3b': { tier: 'SMALL', params: '3B', desc: 'Code-focused model from BigCode.', role: 'Code' },
  'qwen2.5-coder:7b': { tier: 'MEDIUM', params: '7B', desc: 'Balanced performance and quality.', role: 'Code' },
  'codegemma:7b': { tier: 'MEDIUM', params: '7B', desc: "Google's CodeGemma for coding tasks.", role: 'Code' },
  'codellama:7b': { tier: 'MEDIUM', params: '7B', desc: "Meta's code-specialized Llama.", role: 'Code' },
  'deepseek-coder:6.7b': { tier: 'MEDIUM', params: '6.7B', desc: "DeepSeek's mid-tier coder.", role: 'Code' },
  'qwen2.5-coder:14b': { tier: 'LARGE', params: '14B', desc: 'High-quality audits for large projects.', role: 'Code' },
  'codellama:13b': { tier: 'LARGE', params: '13B', desc: 'Larger CodeLlama for thorough audits.', role: 'Code' },
  'deepseek-coder:33b': { tier: 'LARGE', params: '33B', desc: 'Most powerful, for enterprise codebases.', role: 'Code' },
}

const TIER_COLORS = {
  SMALL: { bg: 'rgba(59, 130, 246, 0.1)', border: 'rgba(59, 130, 246, 0.3)', text: '#60A5FA' },
  MEDIUM: { bg: 'rgba(234, 179, 8, 0.1)', border: 'rgba(234, 179, 8, 0.3)', text: '#FBBF24' },
  LARGE: { bg: 'rgba(239, 68, 68, 0.1)', border: 'rgba(239, 68, 68, 0.3)', text: '#F87171' },
}

const RISK_LEVELS = ['HIGH', 'MEDIUM', 'LOW']
const OUTPUT_FORMATS = ['md', 'json', 'sarif']

function Toggle({ label, description, checked, onChange }) {
  return (
    <div className="flex items-center justify-between py-2.5">
      <div>
        <div className="text-sm text-white font-medium">{label}</div>
        {description && <div className="text-[11px] text-muted">{description}</div>}
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={`relative w-10 h-5.5 rounded-full transition-colors ${
          checked ? 'bg-white/30' : 'bg-white/10'
        }`}
      >
        <motion.div
          className="absolute top-0.5 w-4.5 h-4.5 rounded-full bg-white shadow-sm"
          animate={{ left: checked ? '20px' : '2px' }}
          transition={{ duration: 0.2, ease: 'easeOut' }}
          style={{ width: 18, height: 18 }}
        />
      </button>
    </div>
  )
}

function Dropdown({ label, value, options, onChange }) {
  return (
    <div className="flex items-center justify-between py-2.5">
      <div className="text-sm text-white font-medium">{label}</div>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="appearance-none bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 pr-8 text-sm text-white outline-none focus:border-white/20 cursor-pointer"
        >
          {options.map(opt => (
            <option key={opt} value={opt} className="bg-neutral-900">{opt}</option>
          ))}
        </select>
        <ChevronDown size={12} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none" />
      </div>
    </div>
  )
}

function NumberInput({ label, description, value, onChange, min, max, step = 1 }) {
  return (
    <div className="flex items-center justify-between py-2.5">
      <div>
        <div className="text-sm text-white font-medium">{label}</div>
        {description && <div className="text-[11px] text-muted">{description}</div>}
      </div>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
        className="w-20 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white outline-none focus:border-white/20 text-right"
      />
    </div>
  )
}

function TextInput({ label, description, value, onChange, placeholder }) {
  return (
    <div className="py-2.5">
      <div className="text-sm text-white font-medium mb-1">{label}</div>
      {description && <div className="text-[11px] text-muted mb-1.5">{description}</div>}
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-muted outline-none focus:border-white/20"
      />
    </div>
  )
}

export default function SettingsPanel({ config, availableModels, onSave }) {
  // Default config state from dashboard data or defaults
  const defaultConfig = useMemo(() => ({
    model: 'qwen2.5-coder:3b',
    reasoning_model: 'deepseek-r1:1.5b',
    auto_tune: false,
    auto_fix: false,
    fix_code: false,
    skip_rag: false,
    fast_mode: false,
    rotate_models: false,
    turbo: false,
    verbose: false,
    fail_on_risk: 'HIGH',
    output_format: 'md',
    temperature: 0.1,
    include_patterns: '',
    exclude_patterns: '',
    batch_size: 5,
    max_files: 0,
    timeout_per_file: 120,
    custom_rules: [],
    ...(config || {}),
  }), [config])

  const [settings, setSettings] = useState(defaultConfig)
  const [saved, setSaved] = useState(false)
  const [pulling, setPulling] = useState(null)
  const [newRule, setNewRule] = useState('')
  const [activeTab, setActiveTab] = useState('models')
  const [localModelsList, setLocalModelsList] = useState(availableModels || [])

  useEffect(() => {
    setSettings(defaultConfig)
  }, [defaultConfig])

  useEffect(() => {
    setLocalModelsList(availableModels || [])
  }, [availableModels])

  const update = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }))
    setSaved(false)
  }

  const addRule = () => {
    if (newRule.trim()) {
      update('custom_rules', [...(settings.custom_rules || []), newRule.trim()])
      setNewRule('')
    }
  }

  const removeRule = (index) => {
    update('custom_rules', (settings.custom_rules || []).filter((_, i) => i !== index))
  }

  const handlePullModel = async (modelName) => {
    setPulling(modelName)
    try {
      const resp = await fetch('/api/models/pull', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelName }),
      })
      if (resp.ok) {
        setLocalModelsList(prev => [...prev, modelName])
      }
    } catch (e) {
      console.error('Failed to pull model', e)
    } finally {
      setPulling(null)
    }
  }

  const handleSave = async () => {
    try {
      // Try to save via sidecar API
      const resp = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      })
      if (resp.ok) {
        setSaved(true)
        setTimeout(() => setSaved(false), 3000)
        return
      }
    } catch {
      // Sidecar not available — fallback to download
    }

    // Fallback: generate and download dockdesk.yml
    const yamlLines = []
    yamlLines.push('# DockDesk Configuration')
    yamlLines.push('# Generated from Dashboard Settings\n')
    yamlLines.push(`model: ${settings.model}`)
    yamlLines.push(`reasoning_model: ${settings.reasoning_model}`)
    yamlLines.push(`output_format: ${settings.output_format}`)
    yamlLines.push(`fail_on_risk: ${settings.fail_on_risk}`)
    yamlLines.push(`temperature: ${settings.temperature}`)
    yamlLines.push(`auto_tune: ${settings.auto_tune}`)
    yamlLines.push(`auto_fix: ${settings.auto_fix}`)
    yamlLines.push(`fix_code: ${settings.fix_code}`)
    yamlLines.push(`skip_rag: ${settings.skip_rag}`)
    yamlLines.push(`fast_mode: ${settings.fast_mode}`)
    yamlLines.push(`rotate_models: ${settings.rotate_models}`)
    yamlLines.push(`turbo: ${settings.turbo}`)
    yamlLines.push(`verbose: ${settings.verbose}`)
    yamlLines.push(`batch_size: ${settings.batch_size}`)
    yamlLines.push(`max_files: ${settings.max_files}`)
    yamlLines.push(`timeout_per_file: ${settings.timeout_per_file}`)
    if (settings.include_patterns) yamlLines.push(`include_patterns: ${settings.include_patterns}`)
    if (settings.exclude_patterns) yamlLines.push(`exclude_patterns: ${settings.exclude_patterns}`)
    if (settings.custom_rules && settings.custom_rules.length > 0) {
      yamlLines.push('custom_rules:')
      settings.custom_rules.forEach(rule => yamlLines.push(`  - "${rule}"`))
    }

    const blob = new Blob([yamlLines.join('\n') + '\n'], { type: 'text/yaml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'dockdesk.yml'
    a.click()
    URL.revokeObjectURL(url)
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  const resetDefaults = () => {
    setSettings({
      model: 'qwen2.5-coder:3b',
      reasoning_model: 'deepseek-r1:1.5b',
      auto_tune: false,
      auto_fix: false,
      fix_code: false,
      skip_rag: false,
      fast_mode: false,
      rotate_models: false,
      turbo: false,
      verbose: false,
      fail_on_risk: 'HIGH',
      output_format: 'md',
      temperature: 0.1,
      include_patterns: '',
      exclude_patterns: '',
      batch_size: 5,
      max_files: 0,
      timeout_per_file: 120,
      custom_rules: [],
    })
    setSaved(false)
  }

  const localModels = availableModels || []

  const tabs = [
    { id: 'models', label: 'Models', icon: Cpu },
    { id: 'audit', label: 'Audit Config', icon: Settings },
    { id: 'rules', label: 'Custom Rules', icon: Zap },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="glass-card rounded-2xl p-5 border border-white/10">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center space-x-3">
            <div className="w-11 h-11 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center">
              <Settings size={19} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Settings</h2>
              <p className="text-sm text-muted">Configure models and audit options. Changes apply to terminal runs via dockdesk.yml.</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={resetDefaults}
              className="flex items-center gap-1.5 text-xs text-muted hover:text-white px-3 py-2 rounded-lg bg-white/5 border border-white/10 hover:bg-white/[0.08] transition"
            >
              <RotateCcw size={12} />
              Reset
            </button>
            <button
              onClick={handleSave}
              className={`flex items-center gap-1.5 text-xs px-4 py-2 rounded-lg border transition font-medium ${
                saved
                  ? 'bg-green-500/10 border-green-500/30 text-green-400'
                  : 'bg-white/10 border-white/15 text-white hover:bg-white/15'
              }`}
            >
              {saved ? <Check size={13} /> : <Save size={13} />}
              {saved ? 'Saved!' : 'Save Config'}
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-5 bg-white/5 rounded-xl p-1 border border-white/10">
          {tabs.map(tab => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-all flex-1 justify-center ${
                  activeTab === tab.id
                    ? 'bg-white/10 text-white font-medium'
                    : 'text-muted hover:text-white hover:bg-white/5'
                }`}
              >
                <Icon size={14} />
                {tab.label}
              </button>
            )
          })}
        </div>

        {/* Tab content */}
        {activeTab === 'models' && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
            {/* Active model selection */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="rounded-xl bg-white/5 border border-white/10 p-4">
                <div className="text-xs text-muted uppercase tracking-wider mb-2">Code Model</div>
                <div className="text-white font-semibold text-lg">{settings.model}</div>
                <div className="text-[11px] text-muted mt-1">
                  {AUDIT_MODELS[settings.model]?.desc || 'Custom model'}
                </div>
              </div>
              <div className="rounded-xl bg-white/5 border border-white/10 p-4">
                <div className="text-xs text-muted uppercase tracking-wider mb-2">Reasoning Model</div>
                <div className="text-white font-semibold text-lg">{settings.reasoning_model}</div>
                <div className="text-[11px] text-muted mt-1">
                  {AUDIT_MODELS[settings.reasoning_model]?.desc || 'Custom model'}
                </div>
              </div>
            </div>

            {/* Model grid */}
            <div>
              <div className="text-xs text-muted uppercase tracking-wider mb-3">Available Models</div>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                {Object.entries(AUDIT_MODELS).map(([name, model]) => {
                  const isLocal = localModelsList.some(m => m === name || m.split(':')[0] === name.split(':')[0])
                  const isActiveCode = settings.model === name
                  const isActiveReasoning = settings.reasoning_model === name
                  const isPulling = pulling === name
                  const tierStyle = TIER_COLORS[model.tier]

                  return (
                    <div
                      key={name}
                      className={`rounded-xl border p-3.5 transition-all cursor-pointer ${
                        isActiveCode || isActiveReasoning
                          ? 'bg-white/10 border-white/25'
                          : 'bg-white/[0.02] border-white/10 hover:bg-white/5 hover:border-white/15'
                      }`}
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-white font-medium">{name.split(':')[0]}</span>
                          <span className="text-[10px] text-muted font-mono">:{name.split(':')[1]}</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          {isLocal ? (
                            <span className="w-1.5 h-1.5 rounded-full bg-green-400" title="Available locally" />
                          ) : (
                            <span className="w-1.5 h-1.5 rounded-full bg-white/20" title="Not installed" />
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-2 mb-2">
                        <span
                          className="text-[9px] px-1.5 py-0.5 rounded-full font-medium uppercase tracking-wider"
                          style={{ background: tierStyle.bg, color: tierStyle.text, borderWidth: 1, borderColor: tierStyle.border }}
                        >
                          {model.tier}
                        </span>
                        <span className="text-[10px] text-muted font-mono">{model.params}</span>
                        <span className="text-[10px] text-muted">{model.role}</span>
                      </div>

                      <p className="text-[11px] text-muted mb-3 line-clamp-2">{model.desc}</p>

                      <div className="flex gap-2">
                        {isLocal ? (
                          <>
                            {model.role === 'Code' || model.role !== 'Reasoning' ? (
                              <button
                                onClick={() => update('model', name)}
                                className={`flex-1 text-[10px] py-1.5 rounded-lg border transition ${
                                  isActiveCode
                                    ? 'bg-white/15 border-white/25 text-white font-medium'
                                    : 'bg-white/5 border-white/10 text-muted hover:text-white hover:bg-white/8'
                                }`}
                              >
                                {isActiveCode ? '\u2713 Code Model' : 'Set as Code'}
                              </button>
                            ) : null}
                            {model.role === 'Reasoning' || name.includes('deepseek-r1') ? (
                              <button
                                onClick={() => update('reasoning_model', name)}
                                className={`flex-1 text-[10px] py-1.5 rounded-lg border transition ${
                                  isActiveReasoning
                                    ? 'bg-white/15 border-white/25 text-white font-medium'
                                    : 'bg-white/5 border-white/10 text-muted hover:text-white hover:bg-white/8'
                                }`}
                              >
                                {isActiveReasoning ? '\u2713 Reasoning' : 'Set as Reasoning'}
                              </button>
                            ) : null}
                          </>
                        ) : (
                          <button
                            onClick={() => handlePullModel(name)}
                            disabled={pulling !== null}
                            className={`flex-1 flex items-center justify-center gap-1.5 text-[10px] py-1.5 rounded-lg border transition ${
                              isPulling
                                ? 'bg-blue-500/10 border-blue-500/30 text-blue-400'
                                : 'bg-white/5 border-white/10 text-muted hover:text-white hover:bg-white/8'
                            } ${pulling !== null && !isPulling ? 'opacity-50 cursor-not-allowed' : ''}`}
                          >
                            {isPulling ? (
                              <>
                                <Loader2 size={12} className="animate-spin" />
                                Pulling...
                              </>
                            ) : (
                              <>
                                <Download size={12} />
                                Pull Model
                              </>
                            )}
                          </button>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </motion.div>
        )}

        {activeTab === 'audit' && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-1">
            <div className="rounded-xl bg-white/[0.02] border border-white/10 px-4 divide-y divide-white/5">
              <Dropdown label="Fail on Risk" value={settings.fail_on_risk} options={RISK_LEVELS} onChange={(v) => update('fail_on_risk', v)} />
              <Dropdown label="Output Format" value={settings.output_format} options={OUTPUT_FORMATS} onChange={(v) => update('output_format', v)} />
              <NumberInput label="Temperature" description="LLM temperature (0.0 - 1.0)" value={settings.temperature} min={0} max={1} step={0.05} onChange={(v) => update('temperature', v)} />
              <NumberInput label="Batch Size" description="Files per batched LLM call" value={settings.batch_size} min={1} max={20} onChange={(v) => update('batch_size', v)} />
              <NumberInput label="Max Files" description="0 = no limit" value={settings.max_files} min={0} max={10000} onChange={(v) => update('max_files', v)} />
              <NumberInput label="Timeout per File" description="Seconds per file" value={settings.timeout_per_file} min={10} max={600} onChange={(v) => update('timeout_per_file', v)} />
            </div>

            <div className="pt-3 rounded-xl bg-white/[0.02] border border-white/10 px-4 divide-y divide-white/5 mt-4">
              <Toggle label="Auto Tune" description="Auto-select model based on codebase size" checked={settings.auto_tune} onChange={(v) => update('auto_tune', v)} />
              <Toggle label="Auto Fix" description="Automatically apply documentation fixes" checked={settings.auto_fix} onChange={(v) => update('auto_fix', v)} />
              <Toggle label="Fix Code" description="Also fix code, not just docs (use with caution)" checked={settings.fix_code} onChange={(v) => update('fix_code', v)} />
              <Toggle label="Skip RAG" description="Bypass contextual search" checked={settings.skip_rag} onChange={(v) => update('skip_rag', v)} />
              <Toggle label="Fast Mode" description="Skip reasoning for LOW-risk findings" checked={settings.fast_mode} onChange={(v) => update('fast_mode', v)} />
              <Toggle label="Rotate Models" description="Round-robin code analysis model per file" checked={settings.rotate_models} onChange={(v) => update('rotate_models', v)} />
              <Toggle label="Turbo" description="Aggressive speed: fast + skip-rag + batch 8 + workers 4" checked={settings.turbo} onChange={(v) => update('turbo', v)} />
              <Toggle label="Verbose" description="Show detailed output during audit" checked={settings.verbose} onChange={(v) => update('verbose', v)} />
            </div>

            <div className="pt-3 space-y-3 mt-4">
              <TextInput
                label="Include Patterns"
                description="Comma-separated globs, e.g. src/**,lib/**"
                value={settings.include_patterns}
                onChange={(v) => update('include_patterns', v)}
                placeholder="src/**,lib/**"
              />
              <TextInput
                label="Exclude Patterns"
                description="Comma-separated globs, e.g. generated/**,vendor/**"
                value={settings.exclude_patterns}
                onChange={(v) => update('exclude_patterns', v)}
                placeholder="generated/**,vendor/**"
              />
            </div>
          </motion.div>
        )}

        {activeTab === 'rules' && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            <div className="rounded-xl bg-white/[0.02] border border-white/10 p-4">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <div className="text-sm text-white font-medium">Custom Audit Rules</div>
                  <div className="text-[11px] text-muted">Rules injected into LLM prompts during audit</div>
                </div>
                <span className="text-[11px] text-muted font-mono">{(settings.custom_rules || []).length} rule(s)</span>
              </div>

              {/* Add new rule */}
              <div className="flex gap-2 mb-4">
                <input
                  type="text"
                  value={newRule}
                  onChange={(e) => setNewRule(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && addRule()}
                  placeholder="e.g. Flag any hardcoded secrets or API keys"
                  className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-muted outline-none focus:border-white/20"
                />
                <button
                  onClick={addRule}
                  disabled={!newRule.trim()}
                  className="flex items-center gap-1 px-3 py-2 rounded-lg bg-white/10 border border-white/15 text-white text-sm hover:bg-white/15 transition disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <Plus size={14} />
                  Add
                </button>
              </div>

              {/* Rules list */}
              {(settings.custom_rules || []).length === 0 ? (
                <div className="text-sm text-muted text-center py-6">
                  No custom rules defined. Add rules above to enforce specific checks during audits.
                </div>
              ) : (
                <div className="space-y-2">
                  {settings.custom_rules.map((rule, index) => (
                    <motion.div
                      key={`${rule}-${index}`}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      className="flex items-center gap-2 bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 group"
                    >
                      <AlertTriangle size={12} className="text-muted flex-shrink-0" />
                      <span className="text-sm text-white/90 flex-1">{rule}</span>
                      <button
                        onClick={() => removeRule(index)}
                        className="text-muted hover:text-red-400 opacity-0 group-hover:opacity-100 transition"
                      >
                        <X size={14} />
                      </button>
                    </motion.div>
                  ))}
                </div>
              )}
            </div>

            {/* Preset rules */}
            <div className="rounded-xl bg-white/[0.02] border border-white/10 p-4">
              <div className="text-xs text-muted uppercase tracking-wider mb-3">Quick Add Presets</div>
              <div className="flex flex-wrap gap-2">
                {[
                  'Flag any hardcoded secrets or API keys in code',
                  'Ensure all public functions have docstrings',
                  'Check that error handling matches documentation',
                  'Verify all TODO/FIXME comments have issue references',
                  'Flag functions exceeding 50 lines',
                  'Ensure no deprecated APIs are used',
                ].map(preset => (
                  <button
                    key={preset}
                    onClick={() => {
                      if (!(settings.custom_rules || []).includes(preset)) {
                        update('custom_rules', [...(settings.custom_rules || []), preset])
                      }
                    }}
                    disabled={(settings.custom_rules || []).includes(preset)}
                    className="text-[11px] text-muted hover:text-white px-2.5 py-1.5 rounded-lg bg-white/5 border border-white/10 hover:bg-white/[0.08] transition disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    + {preset.length > 40 ? preset.slice(0, 38) + '\u2026' : preset}
                  </button>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  )
}
