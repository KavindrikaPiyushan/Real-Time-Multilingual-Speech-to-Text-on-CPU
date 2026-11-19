import { cardClass, SectionTitle } from './AudioUploader.jsx'

const STATUS_TEXT = {
  idle: 'Waiting for a file',
  reading: 'Reading and checking the WAV file…',
  connecting: 'Connecting to the backend…',
  streaming: 'Streaming audio, transcript updates as it arrives',
  finishing: 'Audio sent, waiting for the final transcript…',
  done: 'Finished',
  error: 'Stopped because of an error',
  cancelled: 'Stopped',
}

const STATUS_COLOR = {
  streaming: ['bg-emerald-500/10 text-emerald-700 dark:text-emerald-300', 'bg-emerald-500 live-dot'],
  finishing: ['bg-amber-500/10 text-amber-700 dark:text-amber-300', 'bg-amber-500'],
  done: ['bg-indigo-500/10 text-indigo-700 dark:text-indigo-300', 'bg-indigo-500'],
  error: ['bg-rose-500/10 text-rose-700 dark:text-rose-300', 'bg-rose-500'],
}
const DEFAULT_COLOR = ['bg-slate-500/10 text-slate-600 dark:text-slate-300', 'bg-slate-400']

export default function Transcript({ state }) {
  const { status, text, committed, error, detectedLanguage } = state
  // `committed` is permanent text, the rest may still change while streaming
  const stable = text.startsWith(committed) ? committed : ''
  const changing = text.slice(stable.length)
  const [pill, dot] = STATUS_COLOR[status] ?? DEFAULT_COLOR

  return (
    <section className={cardClass}>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <SectionTitle n="2">Transcript</SectionTitle>
        <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ${pill}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
          {STATUS_TEXT[status]}
        </span>
      </div>

      {error && (
        <div role="alert" className="mb-3 rounded-xl border border-rose-300/60 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-300">
          <strong>{error.code}:</strong> {error.message}
        </div>
      )}

      <div className="min-h-36 rounded-xl border border-slate-200/70 bg-slate-50/80 p-5 text-lg leading-relaxed dark:border-white/10 dark:bg-black/20" lang={detectedLanguage ?? undefined}>
        {text ? (
          <>
            <span>{stable}</span>
            {changing && (
              <span className={status === 'done' ? '' : 'italic text-slate-400 dark:text-slate-500'}>
                {stable && !/^\s/.test(changing) && !/[⺀-￿]/.test(changing[0]) ? ' ' : ''}{changing.trimStart()}
              </span>
            )}
            {status === 'streaming' && <span className="caret ml-0.5 inline-block h-5 w-0.5 translate-y-1 bg-indigo-500" />}
          </>
        ) : (
          <span className="text-slate-400 dark:text-slate-500">The transcript will appear here.</span>
        )}
      </div>
      <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
        {detectedLanguage && <>Language: <span className="font-medium">{detectedLanguage}</span>. </>}
        {status !== 'done' && text && 'Grey italic text may still change as more audio arrives.'}
      </p>
    </section>
  )
}
