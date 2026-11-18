const sec = (ms) => (ms == null ? '—' : `${(ms / 1000).toFixed(2)} s`)

function Stat({ label, value, hint }) {
  return (
    <div className="rounded-md bg-slate-50 p-3" title={hint}>
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-xl font-semibold tabular-nums">{value}</div>
    </div>
  )
}

export default function PerformanceMetrics({ state }) {
  const { updates, firstTextMs, finalLatencyMs, final } = state
  const last = updates.at(-1)
  // how far the transcript is behind the audio the server has received
  const lag = last ? Math.max(0, last.received - last.covered) : null

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="mb-3 text-lg font-semibold">3. Latency and performance</h2>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="First text after" value={sec(firstTextMs)} hint="Stream start until the first recognised text appeared (measured in the browser)" />
        <Stat label="Final text after end" value={sec(finalLatencyMs)} hint="Last audio chunk sent until the final transcript arrived (browser)" />
        <Stat label="Transcript behind audio" value={lag == null ? '—' : `${lag.toFixed(1)} s`} hint="Audio received by the server but not yet in the latest transcript" />
        <Stat label="Last update took" value={last ? `${last.processing.toFixed(2)} s` : '—'} hint="Server time for the latest transcription pass" />
      </div>

      {final && (
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Real-time factor" value={final.rtf ?? '—'} hint="Total model time / audio length. Below 1 = faster than real time" />
          <Stat label="Model time" value={`${final.total_inference_seconds} s`} hint={`${final.inferences} transcription passes`} />
          <Stat label="Server CPU" value={`${Math.round(final.process_cpu_percent)}%`} hint="Backend process CPU since the last sample (100% = one core)" />
          <Stat label="Server RAM" value={`${final.process_rss_mb} MB`} hint="Backend process memory" />
        </div>
      )}

      {updates.length > 0 && (
        <details className="mt-4 text-sm" open>
          <summary className="cursor-pointer font-medium text-slate-700">Transcript updates ({updates.length})</summary>
          <table className="mt-2 w-full text-left tabular-nums">
            <thead className="text-xs text-slate-500">
              <tr><th>At</th><th>Audio received</th><th>Window</th><th>Took</th></tr>
            </thead>
            <tbody>
              {updates.slice(-8).map((u, i) => (
                <tr key={`${u.t}-${i}`} className="border-t border-slate-100">
                  <td>{sec(u.t)}</td><td>{u.received.toFixed(1)} s</td>
                  <td>{u.window.toFixed(1)} s</td><td>{u.processing.toFixed(2)} s</td>
                </tr>
              ))}
            </tbody>
          </table>
          {updates.length > 8 && <p className="mt-1 text-xs text-slate-400">Showing the last 8.</p>}
        </details>
      )}
    </section>
  )
}
