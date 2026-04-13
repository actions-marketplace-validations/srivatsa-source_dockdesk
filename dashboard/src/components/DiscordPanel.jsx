import { useState, useEffect } from 'react'
import { MessageCircle, Send, CheckCircle, XCircle, Clock, Bell, Settings, ExternalLink } from 'lucide-react'

export default function DiscordPanel() {
  const [webhookUrl, setWebhookUrl] = useState('')
  const [testStatus, setTestStatus] = useState(null) // 'sending', 'success', 'error'
  const [lastPost, setLastPost] = useState(null)

  // Load from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('dockdesk_discord_webhook')
    if (saved) setWebhookUrl(saved)
    const lastTime = localStorage.getItem('dockdesk_discord_last_post')
    if (lastTime) setLastPost(JSON.parse(lastTime))
  }, [])

  const saveWebhook = () => {
    localStorage.setItem('dockdesk_discord_webhook', webhookUrl)
  }

  const sendTestPing = async () => {
    if (!webhookUrl) return
    setTestStatus('sending')

    try {
      const embed = {
        title: '🛡️ DockDesk Test Notification',
        color: 0x6366f1,
        description: 'Your Discord webhook is correctly configured! DockDesk will now send audit summaries and push guard notifications to this channel.',
        fields: [
          { name: 'Status', value: '✅ Connected', inline: true },
          { name: 'Timestamp', value: new Date().toLocaleString(), inline: true },
        ],
        footer: { text: 'DockDesk Neural Auditor — Dashboard Integration' },
        timestamp: new Date().toISOString(),
      }

      const resp = await fetch(webhookUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ embeds: [embed] }),
      })

      if (resp.ok || resp.status === 204) {
        setTestStatus('success')
        const now = { time: new Date().toISOString(), success: true }
        setLastPost(now)
        localStorage.setItem('dockdesk_discord_last_post', JSON.stringify(now))
        saveWebhook()
      } else {
        setTestStatus('error')
        const now = { time: new Date().toISOString(), success: false, error: `HTTP ${resp.status}` }
        setLastPost(now)
        localStorage.setItem('dockdesk_discord_last_post', JSON.stringify(now))
      }
    } catch (err) {
      setTestStatus('error')
      const now = { time: new Date().toISOString(), success: false, error: err.message }
      setLastPost(now)
      localStorage.setItem('dockdesk_discord_last_post', JSON.stringify(now))
    }

    setTimeout(() => setTestStatus(null), 3000)
  }

  const features = [
    {
      icon: Bell,
      title: 'Audit Summaries',
      desc: 'Automatic color-coded embeds after every audit run — shows pass/fail counts, risk distribution, and per-file status.',
    },
    {
      icon: XCircle,
      title: 'Push Guard Alerts',
      desc: 'Red alert when pre-push hook blocks a push due to HIGH risk findings. Team gets notified instantly.',
    },
    {
      icon: CheckCircle,
      title: 'Push Approvals',
      desc: 'Green confirmation when push passes all audit checks. Track deployment safety in your channel.',
    },
  ]

  return (
    <div className="space-y-6">
      {/* Webhook Configuration */}
      <div className="bg-surface-600 border border-white/5 rounded-xl p-6">
        <div className="flex items-center space-x-2 mb-1">
          <MessageCircle size={16} className="text-indigo-400" />
          <h3 className="text-sm font-semibold text-white">Discord Integration</h3>
        </div>
        <p className="text-xs text-muted mb-5">
          Connect DockDesk to your Discord channel for real-time audit notifications.
        </p>

        <div className="space-y-4">
          {/* Webhook URL input */}
          <div>
            <label className="block text-xs text-muted font-medium mb-1.5">Webhook URL</label>
            <div className="flex space-x-2">
              <input
                type="url"
                value={webhookUrl}
                onChange={(e) => setWebhookUrl(e.target.value)}
                placeholder="https://discord.com/api/webhooks/..."
                className="flex-1 bg-surface-700 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition"
              />
              <button
                onClick={sendTestPing}
                disabled={!webhookUrl || testStatus === 'sending'}
                className={`inline-flex items-center space-x-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  !webhookUrl
                    ? 'bg-white/5 text-slate-600 cursor-not-allowed'
                    : testStatus === 'success'
                    ? 'bg-emerald-600 text-white'
                    : testStatus === 'error'
                    ? 'bg-red-600 text-white'
                    : 'bg-indigo-600 hover:bg-indigo-500 text-white'
                }`}
              >
                {testStatus === 'sending' ? (
                  <>
                    <Send size={14} className="animate-pulse" />
                    <span>Sending...</span>
                  </>
                ) : testStatus === 'success' ? (
                  <>
                    <CheckCircle size={14} />
                    <span>Sent!</span>
                  </>
                ) : testStatus === 'error' ? (
                  <>
                    <XCircle size={14} />
                    <span>Failed</span>
                  </>
                ) : (
                  <>
                    <Send size={14} />
                    <span>Send Test</span>
                  </>
                )}
              </button>
            </div>
            <p className="text-[10px] text-slate-600 mt-1.5">
              Create a webhook in Discord: Server Settings → Integrations → Webhooks → New Webhook
            </p>
          </div>

          {/* Status indicator */}
          {lastPost && (
            <div className={`flex items-center space-x-2 text-xs px-3 py-2 rounded-lg ${
              lastPost.success ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
            }`}>
              {lastPost.success ? <CheckCircle size={14} /> : <XCircle size={14} />}
              <span>
                Last test: {new Date(lastPost.time).toLocaleString()}
                {lastPost.error ? ` — ${lastPost.error}` : ' — Success'}
              </span>
            </div>
          )}

          {/* CLI configuration note */}
          <div className="bg-surface-700 border border-white/5 rounded-lg p-4">
            <div className="flex items-center space-x-2 mb-2">
              <Settings size={14} className="text-slate-400" />
              <span className="text-xs text-white font-semibold">CLI Configuration</span>
            </div>
            <p className="text-[11px] text-muted mb-2">
              For automatic notifications on every audit, set the webhook in your CLI config:
            </p>
            <code className="block text-[11px] text-indigo-400 bg-black/30 rounded px-3 py-2 font-mono">
              dockdesk config set discord_webhook &lt;your-webhook-url&gt;
            </code>
          </div>
        </div>
      </div>

      {/* What Gets Posted */}
      <div className="bg-surface-600 border border-white/5 rounded-xl p-6">
        <h4 className="text-sm font-semibold text-white mb-4">What Gets Posted</h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {features.map((feat) => {
            const Icon = feat.icon
            return (
              <div key={feat.title} className="bg-surface-700 rounded-lg p-4 border border-white/5">
                <Icon size={20} className="text-indigo-400 mb-3" />
                <h5 className="text-xs font-semibold text-white mb-1">{feat.title}</h5>
                <p className="text-[11px] text-muted leading-relaxed">{feat.desc}</p>
              </div>
            )
          })}
        </div>
      </div>

      {/* Discord embed preview */}
      <div className="bg-surface-600 border border-white/5 rounded-xl p-6">
        <h4 className="text-sm font-semibold text-white mb-4">Embed Preview</h4>
        <div className="bg-[#2b2d31] rounded-lg p-4 max-w-lg border-l-4 border-indigo-500">
          <div className="text-sm font-semibold text-white mb-2">🛡️ DockDesk Audit — Medium Risk</div>
          <div className="text-xs text-slate-300 mb-3">🧠 <strong>Code:</strong> <code className="text-indigo-300">qwen2.5-coder:7b</code> | <strong>Reasoning:</strong> <code className="text-indigo-300">deepseek-r1:1.5b</code></div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-slate-400">Summary</span>
              <p className="text-slate-200">✅ 3 Pass | ❌ 2 Fail | ⚠️ 1 Error</p>
            </div>
            <div>
              <span className="text-slate-400">Risk</span>
              <p className="text-slate-200">🔴 1 HIGH | 🟡 2 MED | 🟢 3 LOW</p>
            </div>
          </div>
          <div className="mt-3 pt-2 border-t border-white/10 text-[10px] text-slate-500">
            DockDesk Neural Auditor • Today at {new Date().toLocaleTimeString()}
          </div>
        </div>
      </div>
    </div>
  )
}
