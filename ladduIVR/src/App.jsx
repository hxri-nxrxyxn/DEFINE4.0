import React, { useState, useEffect } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { Smartphone, Laptop, CheckCircle2, AlertCircle } from 'lucide-react'
import { cn } from './lib/utils'

export default function App() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadStatus = async () => {
    try {
      const res = await invoke('get_status')
      setStatus(res)
      setError(null)
    } catch (err) {
      console.error('Status fetch error:', err)
      setError(String(err))
    } finally {
      if (initialLoading) {
        setInitialLoading(false)
      }
    }
  }

  useEffect(() => {
    loadStatus()
    const interval = setInterval(() => {
      loadStatus()
    }, 3000)
    return () => clearInterval(interval)
  }, [])

  const handleSelectMode = async (targetMode) => {
    if (loading || status?.mode === targetMode) return
    setLoading(true)
    try {
      const updated = await invoke('switch_mode', { targetMode })
      setStatus(updated)
      setError(null)
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  const isHandsFree = status?.mode === 'handsfree'

  return (
    <div className="min-h-screen bg-black text-zinc-100 flex flex-col font-sans antialiased selection:bg-zinc-800">
      {/* Minimal Header */}
      <header className="border-b border-zinc-900 bg-zinc-950/80 px-6 py-4">
        <h1 className="text-xs font-semibold tracking-wider text-zinc-400 uppercase">
          Bluetooth Audio Mode
        </h1>
      </header>

      {/* Main Single Card Content */}
      <main className="flex-1 flex flex-col justify-center p-6 max-w-xl w-full mx-auto">
        {error && (
          <div className="mb-4 rounded-lg border border-red-900/50 bg-red-950/30 p-3 text-xs text-red-200 flex items-center gap-2">
            <AlertCircle className="h-4 w-4 text-red-400 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Operating Profile Primary Tile */}
        <div className="rounded-xl border border-zinc-850 bg-zinc-950 p-6 shadow-sm">
          <div className="pb-5 border-b border-zinc-900">
            <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-400">
              Operating Profile
            </span>
            <h2 className="text-lg font-medium tracking-tight text-zinc-100 mt-1">
              {initialLoading
                ? 'Detecting profile...'
                : isHandsFree
                ? 'Hands-Free Phone Routing'
                : 'Normal Laptop Audio'}
            </h2>
          </div>

          {/* Interactive Tiles */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 pt-5">
            {/* Hands Free Tile */}
            <button
              type="button"
              onClick={() => handleSelectMode('handsfree')}
              disabled={loading}
              className={cn(
                "relative rounded-lg border p-4 text-left transition-all cursor-pointer flex flex-col justify-between group",
                isHandsFree
                  ? "border-zinc-200 bg-zinc-900/90 text-zinc-100 shadow-sm"
                  : "border-zinc-850 bg-zinc-950 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200",
                loading && "opacity-60 cursor-wait"
              )}
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Smartphone
                      className={cn("h-4 w-4", isHandsFree ? "text-white" : "text-zinc-400")}
                    />
                    <span className="text-sm font-semibold tracking-tight">
                      Hands-Free
                    </span>
                  </div>
                  {isHandsFree && <CheckCircle2 className="h-4 w-4 text-white shrink-0" />}
                </div>
                <p className="text-xs leading-relaxed text-zinc-400">
                  Phone calls route through laptop microphone & speakers.
                </p>
              </div>

              <div className="pt-3 mt-3 border-t border-zinc-900 flex items-center justify-between text-[11px] font-mono text-zinc-400">
                <span>HFP/HSP</span>
                <span className={cn(isHandsFree ? "text-white font-medium" : "text-zinc-400")}>
                  {isHandsFree ? "ACTIVE" : "INACTIVE"}
                </span>
              </div>
            </button>

            {/* Normal Laptop Mode Tile */}
            <button
              type="button"
              onClick={() => handleSelectMode('normal')}
              disabled={loading}
              className={cn(
                "relative rounded-lg border p-4 text-left transition-all cursor-pointer flex flex-col justify-between group",
                !isHandsFree && !initialLoading
                  ? "border-zinc-200 bg-zinc-900/90 text-zinc-100 shadow-sm"
                  : "border-zinc-850 bg-zinc-950 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200",
                loading && "opacity-60 cursor-wait"
              )}
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Laptop
                      className={cn("h-4 w-4", !isHandsFree ? "text-white" : "text-zinc-400")}
                    />
                    <span className="text-sm font-semibold tracking-tight">
                      Normal Laptop
                    </span>
                  </div>
                  {!isHandsFree && !initialLoading && (
                    <CheckCircle2 className="h-4 w-4 text-white shrink-0" />
                  )}
                </div>
                <p className="text-xs leading-relaxed text-zinc-400">
                  Standard media audio. Phone calls remain on your mobile.
                </p>
              </div>

              <div className="pt-3 mt-3 border-t border-zinc-900 flex items-center justify-between text-[11px] font-mono text-zinc-400">
                <span>A2DP</span>
                <span className={cn(!isHandsFree ? "text-white font-medium" : "text-zinc-400")}>
                  {!isHandsFree ? "ACTIVE" : "INACTIVE"}
                </span>
              </div>
            </button>
          </div>
        </div>
      </main>
    </div>
  )
}
