import React, { useState, useEffect } from 'react'
import { invoke } from '@tauri-apps/api/core'
import {
  Smartphone,
  Laptop,
  Radio,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Terminal,
  ChevronRight,
  ShieldCheck,
  Cpu,
  Layers,
  ArrowRightLeft
} from 'lucide-react'
import { cn } from './lib/utils'

export default function App() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)
  const [logs, setLogs] = useState([])
  const [error, setError] = useState(null)

  const addLog = (msg, type = 'info') => {
    const timestamp = new Date().toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
    setLogs(prev => [{ id: Math.random().toString(36).substring(7), timestamp, text: msg, type }, ...prev.slice(0, 49)])
  }

  const loadStatus = async (isBackground = false) => {
    try {
      const res = await invoke('get_status')
      setStatus(res)
      setError(null)
      if (initialLoading) {
        addLog(`System initialized. Current mode: ${res.mode.toUpperCase()}`, 'system')
      }
    } catch (err) {
      console.error('Status fetch error:', err)
      setError(String(err))
      if (!isBackground) {
        addLog(`Failed to query Bluetooth state: ${err}`, 'error')
      }
    } finally {
      if (initialLoading) {
        setInitialLoading(false)
      }
    }
  }

  useEffect(() => {
    loadStatus()
    const interval = setInterval(() => {
      loadStatus(true)
    }, 3500)
    return () => clearInterval(interval)
  }, [])

  const handleToggle = async () => {
    if (loading) return
    setLoading(true)
    const targetMode = status?.mode === 'handsfree' ? 'normal' : 'handsfree'
    addLog(`Initiating mode switch to ${targetMode.toUpperCase()}...`, 'action')
    try {
      const updated = await invoke('switch_mode', { targetMode })
      setStatus(updated)
      addLog(`Bluetooth roles reconfigured. Mode is now ${updated.mode.toUpperCase()}.`, 'success')
      addLog('Audio server pipewire & wireplumber daemon reloaded.', 'system')
    } catch (err) {
      addLog(`Error switching mode: ${err}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleDirectSelect = async (mode) => {
    if (loading || status?.mode === mode) return
    setLoading(true)
    addLog(`Setting operating profile to ${mode.toUpperCase()}...`, 'action')
    try {
      const updated = await invoke('switch_mode', { targetMode: mode })
      setStatus(updated)
      addLog(`Profile successfully configured to ${mode.toUpperCase()}.`, 'success')
    } catch (err) {
      addLog(`Error setting mode: ${err}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleRestartAudio = async () => {
    if (loading) return
    setLoading(true)
    addLog('Restarting user audio subsystem...', 'action')
    try {
      const msg = await invoke('restart_audio_stack')
      addLog(msg, 'success')
      await loadStatus()
    } catch (err) {
      addLog(`Restart failed: ${err}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  const isHandsFree = status?.mode === 'handsfree'

  return (
    <div className="min-h-screen bg-black text-zinc-100 flex flex-col font-sans antialiased border border-zinc-900 selection:bg-zinc-800">
      {/* Top Application Bar / Header */}
      <header className="border-b border-zinc-800 bg-zinc-950/80 px-6 py-4 backdrop-blur supports-[backdrop-filter]:bg-zinc-950/60 sticky top-0 z-10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-2 w-2 rounded-full bg-emerald-400 ring-4 ring-emerald-400/20" />
            <h1 className="text-sm font-semibold tracking-tight text-zinc-100 uppercase">
              Bluetooth Telephony Controller
            </h1>
          </div>
        </div>
      </header>

      {/* Main Body */}
      <main className="flex-1 p-6 space-y-6 max-w-4xl w-full mx-auto">
        {/* Error Notification if any */}
        {error && (
          <div className="rounded-lg border border-red-900/50 bg-red-950/30 p-4 text-xs text-red-200 flex items-start gap-3">
            <AlertCircle className="h-4 w-4 text-red-400 mt-0.5 shrink-0" />
            <div>
              <div className="font-medium text-red-300">Backend Communication Warning</div>
              <div className="text-red-400/80 mt-0.5">{error}</div>
            </div>
          </div>
        )}

        {/* Primary Status & Mode Card */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6 shadow-sm">
          <div className="pb-4 border-b border-zinc-800/80">
            <div className="space-y-1">
              <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-400">
                Operating Profile
              </span>
              <h2 className="text-lg font-medium tracking-tight text-zinc-100">
                {initialLoading ? 'Detecting profile...' : isHandsFree ? 'Hands-Free Phone Routing' : 'Normal Laptop Audio'}
              </h2>
            </div>
          </div>

          {/* Mode Selector Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-5">
            {/* Hands Free Option */}
            <div
              onClick={() => handleDirectSelect('handsfree')}
              className={cn(
                "group relative rounded-lg border p-4 transition-all cursor-pointer flex flex-col justify-between",
                isHandsFree
                  ? "border-zinc-200 bg-zinc-900/80 text-zinc-100 shadow-sm"
                  : "border-zinc-800 bg-zinc-950/40 text-zinc-400 hover:border-zinc-700 hover:text-zinc-300"
              )}
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Smartphone className={cn("h-4 w-4", isHandsFree ? "text-white" : "text-zinc-500")} />
                    <span className="text-sm font-semibold tracking-tight">Hands-Free Telephony</span>
                  </div>
                  {isHandsFree && (
                    <CheckCircle2 className="h-4 w-4 text-white" />
                  )}
                </div>
                <p className="text-xs leading-relaxed text-zinc-400">
                  Bidirectional call routing. Microphone and speaker streams route between this laptop and connected phone.
                </p>
              </div>
              <div className="pt-3 mt-2 border-t border-zinc-800/60 flex items-center justify-between text-[11px] font-mono text-zinc-400">
                <span>HFP/HSP Profile</span>
                <span className={cn(isHandsFree ? "text-white font-medium" : "text-zinc-400")}>
                  {isHandsFree ? "ACTIVE" : "INACTIVE"}
                </span>
              </div>
            </div>

            {/* Normal Laptop Option */}
            <div
              onClick={() => handleDirectSelect('normal')}
              className={cn(
                "group relative rounded-lg border p-4 transition-all cursor-pointer flex flex-col justify-between",
                !isHandsFree && !initialLoading
                  ? "border-zinc-200 bg-zinc-900/80 text-zinc-100 shadow-sm"
                  : "border-zinc-800 bg-zinc-950/40 text-zinc-400 hover:border-zinc-700 hover:text-zinc-300"
              )}
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Laptop className={cn("h-4 w-4", !isHandsFree ? "text-white" : "text-zinc-500")} />
                    <span className="text-sm font-semibold tracking-tight">Normal Laptop Mode</span>
                  </div>
                  {!isHandsFree && !initialLoading && (
                    <CheckCircle2 className="h-4 w-4 text-white" />
                  )}
                </div>
                <p className="text-xs leading-relaxed text-zinc-400">
                  Standard A2DP computer audio. Incoming or outgoing phone calls remain entirely on the phone.
                </p>
              </div>
              <div className="pt-3 mt-2 border-t border-zinc-800/60 flex items-center justify-between text-[11px] font-mono text-zinc-400">
                <span>A2DP Standard</span>
                <span className={cn(!isHandsFree ? "text-white font-medium" : "text-zinc-400")}>
                  {!isHandsFree ? "ACTIVE" : "INACTIVE"}
                </span>
              </div>
            </div>
          </div>

          {/* Master Toggle Action */}
          <div className="pt-5 mt-5 border-t border-zinc-800 flex items-center justify-between">
            <div className="text-xs text-zinc-400">
              Click either card above or execute instantaneous toggle:
            </div>
            <button
              onClick={handleToggle}
              disabled={loading || initialLoading}
              className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-zinc-100 px-4 py-2 text-xs font-semibold text-zinc-950 hover:bg-zinc-200 active:scale-[0.99] transition-all disabled:opacity-50 disabled:pointer-events-none shadow-sm cursor-pointer"
            >
              <ArrowRightLeft className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
              <span>
                {loading
                  ? "Reconfiguring Audio Stack..."
                  : isHandsFree
                  ? "Switch to Normal Laptop Mode"
                  : "Switch to Hands-Free Mode"}
              </span>
            </button>
          </div>
        </div>

        {/* Hardware & BlueZ Inspector Section */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Adapter Info */}
          <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4 space-y-3">
            <div className="flex items-center gap-2 text-xs font-mono text-zinc-400 uppercase tracking-wider">
              <Cpu className="h-3.5 w-3.5 text-zinc-400" />
              <span>Adapter Controller</span>
            </div>
            <div className="space-y-1">
              <div className="text-sm font-semibold text-zinc-100 truncate">
                {status?.info?.controller_name || 'pop-os'}
              </div>
              <div className="text-xs font-mono text-zinc-400">
                Class: {status?.info?.class_hex || '0x000000'}
              </div>
            </div>
            <div className="pt-2 border-t border-zinc-850 text-[11px] text-zinc-400 flex items-center justify-between">
              <span>Adapter Power</span>
              <span className="font-mono text-zinc-200">
                {status?.info?.powered ? 'ONLINE' : 'OFFLINE'}
              </span>
            </div>
          </div>

          {/* Profile Definition */}
          <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4 space-y-3">
            <div className="flex items-center gap-2 text-xs font-mono text-zinc-400 uppercase tracking-wider">
              <Layers className="h-3.5 w-3.5 text-zinc-400" />
              <span>Profile Classification</span>
            </div>
            <div className="space-y-1">
              <div className="text-sm font-medium text-zinc-200 line-clamp-1">
                {status?.info?.class || 'Standard Computer'}
              </div>
              <div className="text-xs font-mono text-zinc-400">
                HF UUID: {status?.info?.has_handsfree_uuid ? 'DETECTED' : 'NOT BROADCAST'}
              </div>
            </div>
            <div className="pt-2 border-t border-zinc-850 text-[11px] text-zinc-400 flex items-center justify-between">
              <span>Roles Conf</span>
              <span className="font-mono text-zinc-200">
                {status?.roles_file_exists ? 'CONSTRAINED' : 'DEFAULT'}
              </span>
            </div>
          </div>

          {/* Connected Peripheral */}
          <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4 space-y-3">
            <div className="flex items-center gap-2 text-xs font-mono text-zinc-400 uppercase tracking-wider">
              <Radio className="h-3.5 w-3.5 text-zinc-400" />
              <span>Connected Target</span>
            </div>
            <div>
              {status?.info?.connected_devices && status.info.connected_devices.length > 0 ? (
                status.info.connected_devices.map(d => (
                  <div key={d.mac} className="space-y-0.5">
                    <div className="text-sm font-semibold text-zinc-100 truncate">{d.name}</div>
                    <div className="text-xs font-mono text-zinc-400">{d.mac}</div>
                  </div>
                ))
              ) : (
                <div className="space-y-0.5">
                  <div className="text-sm font-medium text-zinc-400">No Target Paired</div>
                  <div className="text-xs text-zinc-400">Connect phone via Bluetooth</div>
                </div>
              )}
            </div>
            <div className="pt-2 border-t border-zinc-850 text-[11px] text-zinc-400 flex items-center justify-between">
              <span>Count</span>
              <span className="font-mono text-zinc-200">
                {status?.info?.connected_devices?.length || 0} Connected
              </span>
            </div>
          </div>
        </div>

        {/* Real-time Activity Terminal / Log View */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 overflow-hidden shadow-sm">
          <div className="px-4 py-2.5 border-b border-zinc-800 bg-zinc-900/40 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Terminal className="h-3.5 w-3.5 text-zinc-400" />
              <span className="text-xs font-mono uppercase tracking-wider text-zinc-300">
                Subsystem Activity Log
              </span>
            </div>
            <span className="text-[10px] font-mono text-zinc-400">
              {logs.length} entries recorded
            </span>
          </div>

          <div className="p-4 bg-black/90 font-mono text-xs text-zinc-400 h-36 overflow-y-auto space-y-1.5 scrollbar-thin scrollbar-thumb-zinc-800">
            {logs.length === 0 ? (
              <div className="text-zinc-600 text-xs italic">Waiting for events...</div>
            ) : (
              logs.map((item) => (
                <div key={item.id} className="flex items-start gap-2 leading-relaxed">
                  <span className="text-zinc-600 select-none">[{item.timestamp}]</span>
                  <span
                    className={cn(
                      "break-all",
                      item.type === 'error' && "text-red-400",
                      item.type === 'success' && "text-emerald-300",
                      item.type === 'action' && "text-zinc-200 font-semibold",
                      item.type === 'system' && "text-zinc-400",
                      item.type === 'info' && "text-zinc-300"
                    )}
                  >
                    {item.text}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-900 px-6 py-3 text-center text-[11px] font-mono text-zinc-600">
        <span>PipeWire 1.0+ / BlueZ 5.60+ / WirePlumber 0.5+ Daemon Orchestration</span>
      </footer>
    </div>
  )
}
