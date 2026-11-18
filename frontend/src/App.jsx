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
    checking: ['bg-slate-100 text-slate-600', 'Checking backend…'],
    ready: ['bg-emerald-100 text-emerald-800', `Backend ready · ${health.h?.model_id ?? ''} · ${health.h?.active_streams ?? 0} active stream(s)`],
    'no-model': ['bg-amber-100 text-amber-800', 'Backend is up but the model is not loaded'],
    offline: ['bg-rose-100 text-rose-800', `Backend not reachable at ${API_URL}`],
  }[health.state]
  return <span className={`rounded-full px-3 py-1 text-xs font-medium ${look[0]}`}>{look[1]}</span>
}

export default function App() {
  const { state, start, cancel, reset } = useAudioStreaming()

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <main className="mx-auto flex max-w-3xl flex-col gap-5 px-4 py-8">
        <header className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-2xl font-bold">Live speech-to-text on CPU</h1>
            <p className="text-sm text-slate-500">
              Streams a WAV file to Qwen3-ASR in small chunks, like one live call leg.
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
