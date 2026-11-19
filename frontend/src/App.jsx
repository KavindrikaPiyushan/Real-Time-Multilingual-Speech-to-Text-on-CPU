import { useEffect, useState } from 'react'
import AudioUploader from './components/AudioUploader.jsx'
import PerformanceMetrics from './components/PerformanceMetrics.jsx'
import Transcript from './components/Transcript.jsx'
import { useAudioStreaming } from './hooks/useAudioStreaming.js'
import { API_URL, fetchHealth } from './services/websocket.js'

function BackendBadge() {
  const [health, setHealth] = useState({ state: 'checking' })
  useEffect(() => {
    let alive = true
    const check = () => fetchHealth()
      .then((h) => alive && setHealth({ state: h.model_loaded ? 'ready' : 'no-model', h }))
      .catch(() => alive && setHealth({ state: 'offline' }))
    check()
    const id = setInterval(check, 5000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  const look = {
    checking: ['bg-slate-400', 'text-slate-600 dark:text-slate-300', 'Checking backend…'],
    ready: ['bg-emerald-500', 'text-emerald-700 dark:text-emerald-300', `Ready · ${health.h?.model_id ?? ''} · ${health.h?.active_streams ?? 0} active`],
    'no-model': ['bg-amber-500', 'text-amber-700 dark:text-amber-300', 'Backend up, model not loaded'],
    offline: ['bg-rose-500', 'text-rose-700 dark:text-rose-300', `Offline · ${API_URL}`],
  }[health.state]

  return (
    <span className={`inline-flex items-center gap-2 rounded-full border border-slate-200/70 bg-white/70 px-3 py-1.5 text-xs font-medium backdrop-blur dark:border-white/10 dark:bg-white/5 ${look[1]}`}>
      <span className={`h-2 w-2 rounded-full ${look[0]} ${health.state === 'ready' ? 'live-dot' : ''}`} />
      {look[2]}
    </span>
  )
}

export default function App() {
  const { state, start, cancel, reset } = useAudioStreaming()

  return (
    <div className="app-bg min-h-screen text-slate-900 dark:text-slate-100">
      <main className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-10 sm:py-14">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-indigo-500/10 px-3 py-1 text-xs font-semibold text-indigo-600 dark:text-indigo-300">
              <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M4 10v4M8 6v12M12 3v18M16 7v10M20 10v4" />
              </svg>
              Qwen3-ASR · CPU only
            </div>
            <h1 className="bg-gradient-to-r from-slate-900 to-indigo-600 bg-clip-text text-3xl font-bold tracking-tight text-transparent sm:text-4xl dark:from-white dark:to-indigo-300">
              Live speech-to-text
            </h1>
            <p className="mt-2 max-w-md text-sm leading-relaxed text-slate-500 dark:text-slate-400">
              Streams a WAV file to the model in small chunks, like one live call leg.
            </p>
          </div>
          <BackendBadge />
        </header>
        <AudioUploader state={state} onStart={start} onCancel={cancel} onReset={reset} />
        <Transcript state={state} />
        <PerformanceMetrics state={state} />
      </main>
    </div>
  )
}
