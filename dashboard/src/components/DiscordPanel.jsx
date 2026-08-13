import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { MessageCircle, Send, CheckCircle, XCircle, Bell, Settings } from 'lucide-react'

export default function DiscordPanel() {
  const [webhookUrl, setWebhookUrl] = useState('')
  const [testStatus, setTestStatus] = useState(null)
  const [lastPost, setLastPost] = useState(null)

  useEffect(() => {
    const saved = localStorage.getItem('dockdesk_discord_webhook')
    if (saved) setWebhookUrl(saved)
    const lastTime = localStorage.getItem('dockdesk_discord_last_post')
    if (lastTime) setLastPost(JSON.parse(lastTime))
  }, [])

  const saveWebhook = () => localStorage.setItem('dockdesk_discord_webhook', webhookUrl)

  const sendTestPing = async () => {
    if (!webhookUrl) return
    setTestStatus('sending')
    try {
      const embed = {
        title: '\u{1f6e1}\ufe0f DockDesk Test Notification', color: 0x8A2BE2,
        description: 'Your Discord webhook is correctly configured!',
        fields: [
          { name: 'Status', value: '\u2705 Connected', inline: true },
          { name: 'Timestamp', value: new Date().toLocaleString(), inline: true },
        ],
        footer: { text: 'DockDesk Neural Auditor' }, timestamp: new Date().toISOString(),
      }
      const resp = await fetch(webhookUrl, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ embeds: [embed] }) })
      const success = resp.ok || resp.status === 204
      setTestStatus(success ? 'success' : 'error')
      const now = { time: new Date().toISOString(), success, error: success ? null : `HTTP ${resp.status}` }
      setLastPost(now)
      localStorage.setItem('dockdesk_discord_last_post', JSON.stringify(now))
      if (success) saveWebhook()
    } catch (err) {
      setTestStatus('error')
      const now = { time: new Date().toISOString(), success: false, error: err.message }
      setLastPost(now)
      localStorage.setItem('dockdesk_discord_last_post', JSON.stringify(now))
    }
    setTimeout(() => setTestStatus(null), 3000)
  }

  const features = [
    { icon: Bell, title: 'Audit Summaries', desc: 'Color-coded embeds after every audit - pass/fail counts, risk distribution.' },
    { icon: XCircle, title: 'Push Guard Alerts', desc: 'Red alert when pre-push hook blocks a push due to HIGH risk.' },
    { icon: CheckCircle, title: 'Push Approvals', desc: 'Green confirmation when push passes all audit checks.' },
  ]

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card glass-card-hover rounded-xl p-6">
        <div className="flex items-center space-x-2 mb-1">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-purple-500/20 to-pink-500/20 flex items-center justify-center">
            <MessageCircle size={14} className="text-purple-400" />
          </div>
          <h3 className="text-sm font-semibold text-white">Discord Integration</h3>
        </div>
        <p className="text-xs text-muted mb-5">Connect DockDesk to Discord for real-time audit notifications.</p>
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-muted font-medium mb-1.5">Webhook URL</label>
            <div className="flex space-x-2">
              <input type="url" value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} placeholder="https://discord.com/api/webhooks/..."
                className="flex-1 bg-surface-700 border border-purple-500/20 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 outline-none transition" />
              <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} onClick={sendTestPing} disabled={!webhookUrl || testStatus === 'sending'}
                className={`inline-flex items-center space-x-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all ${!webhookUrl ? 'bg-white/5 text-slate-600 cursor-not-allowed' : testStatus === 'success' ? 'bg-emerald-600 text-white' : testStatus === 'error' ? 'bg-red-600 text-white' : 'bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white'}`}>
                {testStatus === 'sending' ? <><Send size={14} className="animate-pulse" /><span>Sending...</span></> : testStatus === 'success' ? <><CheckCircle size={14} /><span>Sent!</span></> : testStatus === 'error' ? <><XCircle size={14} /><span>Failed</span></> : <><Send size={14} /><span>Send Test</span></>}
              </motion.button>
            </div>
            <p className="text-[10px] text-slate-600 mt-1.5">Server Settings &gt; Integrations &gt; Webhooks &gt; New Webhook</p>
          </div>
          {lastPost && (
            <div className={`flex items-center space-x-2 text-xs px-3 py-2 rounded-lg ${lastPost.success ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20' : 'bg-pink-500/10 text-pink-400 border border-pink-500/20'}`}>
              {lastPost.success ? <CheckCircle size={14} /> : <XCircle size={14} />}
              <span>Last: {new Date(lastPost.time).toLocaleString()}{lastPost.error ? ` - ${lastPost.error}` : ' - Success'}</span>
            </div>
          )}
          <div className="glass-card rounded-lg p-4">
            <div className="flex items-center space-x-2 mb-2"><Settings size={14} className="text-purple-400" /><span className="text-xs text-white font-semibold">CLI Configuration</span></div>
            <p className="text-[11px] text-muted mb-2">Set webhook in CLI config for auto-notifications:</p>
            <code className="block text-[11px] text-purple-400 bg-black/30 rounded px-3 py-2 font-mono">dockdesk config set discord_webhook &lt;url&gt;</code>
          </div>
        </div>
      </motion.div>

      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="glass-card glass-card-hover rounded-xl p-6">
        <h4 className="text-sm font-semibold text-white mb-4">What Gets Posted</h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {features.map((feat, i) => {
            const Icon = feat.icon
            return (
              <motion.div key={feat.title} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 + i * 0.08 }} whileHover={{ scale: 1.02 }} className="glass-card rounded-lg p-4">
                <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-purple-500/20 to-pink-500/20 flex items-center justify-center mb-3"><Icon size={18} className="text-purple-400" /></div>
                <h5 className="text-xs font-semibold text-white mb-1">{feat.title}</h5>
                <p className="text-[11px] text-muted leading-relaxed">{feat.desc}</p>
              </motion.div>
            )
          })}
        </div>
      </motion.div>

      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="glass-card glass-card-hover rounded-xl p-6">
        <h4 className="text-sm font-semibold text-white mb-4">Embed Preview</h4>
        <div className="bg-[#2b2d31] rounded-lg p-4 max-w-lg border-l-4 border-purple-500">
          <div className="text-sm font-semibold text-white mb-2">{'\u{1f6e1}\ufe0f'} DockDesk Audit - Medium Risk</div>
          <div className="text-xs text-slate-300 mb-3">{'\u{1f9e0}'} <strong>Code:</strong> <code className="text-purple-300">qwen2.5-coder:7b</code> | <strong>Reasoning:</strong> <code className="text-purple-300">deepseek-r1:1.5b</code></div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div><span className="text-slate-400">Summary</span><p className="text-slate-200">{'\u2705'} 3 Pass | {'\u274c'} 2 Fail</p></div>
            <div><span className="text-slate-400">Risk</span><p className="text-slate-200">{'\u{1f534}'} 1 HIGH | {'\u{1f7e1}'} 2 MED | {'\u{1f7e2}'} 3 LOW</p></div>
          </div>
          <div className="mt-3 pt-2 border-t border-white/10 text-[10px] text-slate-500">DockDesk Neural Auditor • Today at {new Date().toLocaleTimeString()}</div>
        </div>
      </motion.div>
    </div>
  )
}
