import { useRef, useState } from 'react'
import LanguageSelector from './LanguageSelector.jsx'

const BUSY = ['reading', 'connecting', 'streaming', 'finishing']

export const cardClass =
  'rounded-2xl border border-slate-200/70 bg-white/80 p-6 shadow-xl shadow-slate-900/5 backdrop-blur dark:border-white/10 dark:bg-white/[0.04] dark:shadow-black/20'

export function SectionTitle({ n, children }) {
  return (
    <h2 className="flex items-center gap-3 text-base font-semibold">
      <span className="grid h-7 w-7 place-items-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-500 text-xs font-bold text-white shadow-md shadow-indigo-500/30">
        {n}
      </span>
      {children}
    </h2>
  )
}

export default function AudioUploader({ state, onStart, onCancel, onReset }) {
  const [file, setFile] = useState(null)
  const [language, setLanguage] = useState('auto')
  const [chunkMs, setChunkMs] = useState(2000)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)
  const busy = BUSY.includes(state.status)

  const progress = state.file ? Math.min(100, (state.sentSeconds / state.file.durationS) * 100) : 0

  const pick = (f) => { if (f && !busy) setFile(f) }

  return (
    <section className={cardClass}>
      <SectionTitle n="1">Choose audio</SectionTitle>
      <p className="mb-4 mt-2 text-sm text-slate-500 dark:text-slate-400">
        16 kHz, mono, 16-bit Linear PCM WAV (the file is checked before streaming).
      </p>

      <input
        ref={inputRef}
        type="file"
        accept=".wav,audio/wav,audio/x-wav"
        disabled={busy}
        onChange={(e) => pick(e.target.files?.[0] ?? null)}
        className="hidden"
      />

      <button
        type="button"
        disabled={busy}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); pick(e.dataTransfer.files?.[0]) }}
        className={`mb-5 flex w-full flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-4 py-8 text-center transition disabled:cursor-not-allowed disabled:opacity-60 ${
          dragging
            ? 'border-indigo-500 bg-indigo-500/10'
            : 'border-slate-300 hover:border-indigo-400 hover:bg-indigo-500/5 dark:border-white/15'
        }`}
      >
        <span className="grid h-11 w-11 place-items-center rounded-full bg-indigo-500/10 text-indigo-600 dark:text-indigo-300">
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 16V4m0 0L7 9m5-5l5 5M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" />
          </svg>
        </span>
        {file ? (
          <>
            <span className="text-sm font-semibold">{file.name}</span>
            <span className="text-xs text-slate-500 dark:text-slate-400">{(file.size / 1024).toFixed(0)} KB · click to change</span>
          </>
        ) : (
          <>
            <span className="text-sm font-semibold">Drop a WAV file here, or click to browse</span>
            <span className="text-xs text-slate-500 dark:text-slate-400">No file chosen</span>
          </>
        )}
      </button>

      <LanguageSelector
        language={language} onLanguage={setLanguage}
        chunkMs={chunkMs} onChunkMs={setChunkMs} disabled={busy}
      />

      <div className="mt-6 flex flex-wrap gap-3">
        <button
          type="button"
          disabled={!file || busy}
          onClick={() => onStart(file, { language, chunkMs })}
          className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-500 to-violet-500 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/30 transition hover:brightness-110 active:scale-[0.98] disabled:cursor-not-allowed disabled:from-slate-300 disabled:to-slate-300 disabled:shadow-none dark:disabled:from-white/10 dark:disabled:to-white/10 dark:disabled:text-white/40"
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
          Start streaming
        </button>
        {busy && (
          <button type="button" onClick={onCancel} className="rounded-xl bg-rose-500 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-rose-500/25 transition hover:bg-rose-600 active:scale-[0.98]">
            Stop
          </button>
        )}
        {!busy && state.status !== 'idle' && (
          <button
            type="button"
            onClick={() => { onReset(); setFile(null); if (inputRef.current) inputRef.current.value = '' }}
            className="rounded-xl border border-slate-300 px-5 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 dark:border-white/15 dark:text-slate-200 dark:hover:bg-white/10"
          >
            Clear
          </button>
        )}
      </div>

      {state.file && (
        <div className="mt-6 rounded-xl bg-slate-100/80 p-4 text-sm dark:bg-white/5">
          <div className="flex flex-wrap justify-between gap-2 text-slate-600 dark:text-slate-300">
            <span className="font-medium">{state.file.name}</span>
            <span className="tabular-nums text-slate-500 dark:text-slate-400">
              {state.file.durationS.toFixed(1)} s · {(state.file.sizeBytes / 1024).toFixed(0)} KB
            </span>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-white/10" role="progressbar" aria-valuenow={Math.round(progress)}>
            <div className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all" style={{ width: `${progress}%` }} />
          </div>
          <div className="mt-2 text-xs tabular-nums text-slate-500 dark:text-slate-400">
            Sent {state.sentSeconds.toFixed(1)} s of {state.file.durationS.toFixed(1)} s
          </div>
        </div>
      )}
    </section>
  )
}
