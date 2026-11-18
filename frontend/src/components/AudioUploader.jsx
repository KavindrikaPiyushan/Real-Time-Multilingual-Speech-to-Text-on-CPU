import { useRef, useState } from 'react'
import LanguageSelector from './LanguageSelector.jsx'

const BUSY = ['reading', 'connecting', 'streaming', 'finishing']

export default function AudioUploader({ state, onStart, onCancel, onReset }) {
  const [file, setFile] = useState(null)
  const [language, setLanguage] = useState('auto')
  const [chunkMs, setChunkMs] = useState(2000)
  const inputRef = useRef(null)
  const busy = BUSY.includes(state.status)

  const progress = state.file ? Math.min(100, (state.sentSeconds / state.file.durationS) * 100) : 0

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="mb-3 text-lg font-semibold">1. Choose audio</h2>
      <p className="mb-3 text-sm text-slate-500">16 kHz, mono, 16-bit Linear PCM WAV (the file is checked before streaming).</p>

      <input
        ref={inputRef}
        type="file"
        accept=".wav,audio/wav,audio/x-wav"
        disabled={busy}
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        className="mb-4 block w-full text-sm file:mr-3 file:rounded-md file:border-0 file:bg-slate-800 file:px-4 file:py-2 file:text-white"
      />

      <LanguageSelector
        language={language} onLanguage={setLanguage}
        chunkMs={chunkMs} onChunkMs={setChunkMs} disabled={busy}
      />

      <div className="mt-4 flex gap-3">
        <button
          type="button"
          disabled={!file || busy}
          onClick={() => onStart(file, { language, chunkMs })}
          className="rounded-md bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          Start streaming
        </button>
        {busy && (
          <button type="button" onClick={onCancel} className="rounded-md bg-rose-600 px-4 py-2 font-medium text-white hover:bg-rose-700">
            Stop
          </button>
        )}
        {!busy && state.status !== 'idle' && (
          <button
            type="button"
            onClick={() => { onReset(); setFile(null); if (inputRef.current) inputRef.current.value = '' }}
            className="rounded-md border border-slate-300 px-4 py-2 font-medium text-slate-700 hover:bg-slate-50"
          >
            Clear
          </button>
        )}
      </div>

      {state.file && (
        <div className="mt-4 text-sm text-slate-600">
          <div>{state.file.name} · {state.file.durationS.toFixed(1)} s · {(state.file.sizeBytes / 1024).toFixed(0)} KB</div>
          <div className="mt-2 h-2 overflow-hidden rounded bg-slate-200" role="progressbar" aria-valuenow={Math.round(progress)}>
            <div className="h-full bg-emerald-500 transition-all" style={{ width: `${progress}%` }} />
          </div>
          <div className="mt-1">Sent {state.sentSeconds.toFixed(1)} s of {state.file.durationS.toFixed(1)} s</div>
        </div>
      )}
    </section>
  )
}
