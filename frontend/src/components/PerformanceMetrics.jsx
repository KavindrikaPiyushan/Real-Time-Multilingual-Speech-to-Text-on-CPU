import { cardClass, SectionTitle } from './AudioUploader.jsx'

const sec = (ms) => (ms == null ? '—' : `${(ms / 1000).toFixed(2)} s`)

function Stat({ label, value, hint }) {
  return (
    <div className="rounded-xl border border-slate-200/70 bg-slate-50/80 p-4 dark:border-white/10 dark:bg-white/5" title={hint}>
      <div className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums tracking-tight">{value}</div>
    </div>
  )
}

export default function PerformanceMetrics({ state }) {
  const { updates, firstTextMs, finalLatencyMs, final } = state
  const last = updates.at(-1)
  // how far the transcript is behind the audio the server has received
  const lag = last ? Math.max(0, last.received - last.covered) : null

  return (
    <section className={cardClass}>
      <div className="mb-4"><SectionTitle n="3">Latency and performance</SectionTitle></div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="First text after" value={sec(firstTextMs)} hint="Stream start until the first recognised text appeared (measured in the browser)" />
        <Stat label="Final text after end" value={sec(finalLatencyMs)} hint="Last audio chunk sent until the final transcript arrived (browser)" />
        <Stat label="Transcript behind audio" value={lag == null ? '—' : `${lag.toFixed(1)} s`} hint="Audio received by the server but not yet in the latest transcript" />
        <Stat label="Last update took" value={last ? `${last.processing.toFixed(2)} s` : '—'} hint="Server time for the latest transcription pass" />
      </div>

      {final && (
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Real-time factor" value={final.rtf ?? '—'} hint="Total model time / audio length. Below 1 = faster than real time" />
          <Stat label="Model time" value={`${final.total_inference_seconds} s`} hint={`${final.inferences} transcription passes`} />
          <Stat label="Server CPU" value={`${Math.round(final.process_cpu_percent)}%`} hint="Backend process CPU since the last sample (100% = one core)" />
          <Stat label="Server RAM" value={`${final.process_rss_mb} MB`} hint="Backend process memory" />
        </div>
      )}

      {updates.length > 0 && (
        <details className="mt-5 text-sm" open>
          <summary className="cursor-pointer font-medium text-slate-700 dark:text-slate-200">Transcript updates ({updates.length})</summary>
          <div className="mt-3 overflow-x-auto rounded-xl border border-slate-200/70 dark:border-white/10">
            <table className="w-full text-left tabular-nums">
              <thead className="bg-slate-100/80 text-xs uppercase tracking-wide text-slate-500 dark:bg-white/5 dark:text-slate-400">
                <tr>
                  <th className="px-3 py-2 font-medium">At</th>
                  <th className="px-3 py-2 font-medium">Audio received</th>
                  <th className="px-3 py-2 font-medium">Window</th>
                  <th className="px-3 py-2 font-medium">Took</th>
                </tr>
              </thead>
              <tbody>
                {updates.slice(-8).map((u, i) => (
                  <tr key={`${u.t}-${i}`} className="border-t border-slate-100 dark:border-white/5">
                    <td className="px-3 py-2">{sec(u.t)}</td>
                    <td className="px-3 py-2">{u.received.toFixed(1)} s</td>
                    <td className="px-3 py-2">{u.window.toFixed(1)} s</td>
                    <td className="px-3 py-2">{u.processing.toFixed(2)} s</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {updates.length > 8 && <p className="mt-2 text-xs text-slate-400">Showing the last 8.</p>}
        </details>
      )}
    </section>
  )
}
