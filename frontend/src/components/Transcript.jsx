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
  streaming: 'bg-emerald-100 text-emerald-800',
  finishing: 'bg-amber-100 text-amber-800',
  done: 'bg-blue-100 text-blue-800',
  error: 'bg-rose-100 text-rose-800',
}

export default function Transcript({ state }) {
  const { status, text, committed, error, detectedLanguage } = state
  // `committed` is permanent text, the rest may still change while streaming
  const stable = text.startsWith(committed) ? committed : ''
  const changing = text.slice(stable.length)

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">2. Transcript</h2>
        <span className={`rounded-full px-3 py-1 text-xs font-medium ${STATUS_COLOR[status] ?? 'bg-slate-100 text-slate-600'}`}>
          {STATUS_TEXT[status]}
        </span>
      </div>

      {error && (
        <div role="alert" className="mb-3 rounded-md border border-rose-300 bg-rose-50 p-3 text-sm text-rose-800">
          <strong>{error.code}:</strong> {error.message}
        </div>
      )}

      <div className="min-h-32 rounded-md bg-slate-50 p-4 text-lg leading-relaxed" lang={detectedLanguage ?? undefined}>
        {text ? (
          <>
            <span>{stable}</span>
            {changing && (
              <span className={status === 'done' ? '' : 'text-slate-500 italic'}>
                {stable && !/^\s/.test(changing) && !/[⺀-￿]/.test(changing[0]) ? ' ' : ''}{changing.trimStart()}
              </span>
            )}
          </>
        ) : (
          <span className="text-slate-400">The transcript will appear here.</span>
        )}
      </div>
      <p className="mt-2 text-xs text-slate-500">
        {detectedLanguage && <>Language: {detectedLanguage}. </>}
        {status !== 'done' && text && 'Grey italic text may still change as more audio arrives.'}
      </p>
    </section>
  )
}
