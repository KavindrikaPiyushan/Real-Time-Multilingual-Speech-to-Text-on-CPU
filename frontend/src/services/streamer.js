// Streams a parsed WAV to the backend like a live call. No React in here, so it can be tested alone.
import { chunkBounds } from './wav.js'
import { openStream, WS_URL } from './websocket.js'

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

/**
 * Stream `wav` (from parseWav) to the backend and report progress through onEvent.
 * Chunks are sent at real-time speed: each chunk is sent once its audio would have been spoken.
 *
 * Events: connecting | streaming | sent | server (any message from the backend) | ending
 *         | done | error | cancelled      (every event carries `t`: ms since the stream became ready)
 * Resolves with the last event (done / error / cancelled).
 */
export function streamWav({
  wav, language = 'auto', chunkMs = 2000, url = WS_URL, onEvent = () => {}, signal,
  pace = true, open = openStream,
}) {
  return new Promise((resolve) => {
    let conn = null
    let t0 = performance.now()
    let finished = false
    const t = () => Math.round(performance.now() - t0)

    const finish = (event) => {
      if (finished) return
      finished = true
      const full = { ...event, t: t() }
      onEvent(full)
      try { conn?.close() } catch { /* already closed */ }
      resolve(full)
    }

    const sendAudio = async () => {
      const bounds = chunkBounds(wav.pcm.length, wav.bytesPerSecond, chunkMs)
      for (const [start, end] of bounds) {
        if (pace) {
          // wait until this chunk's audio has "been spoken", like a live call
          const wait = t0 + (end / wav.bytesPerSecond) * 1000 - performance.now()
          if (wait > 0) await sleep(wait)
        }
        if (finished) return
        if (!conn.open) return finish({ type: 'error', code: 'connection_lost', message: 'Connection to the server was lost while sending audio.' })
        conn.sendBinary(wav.pcm.subarray(start, end))
        onEvent({ type: 'sent', sentSeconds: end / wav.bytesPerSecond, t: t() })
      }
      if (finished) return
      conn.sendJson({ type: 'end' })
      onEvent({ type: 'ending', t: t() })
    }

    const handle = (msg) => {
      if (finished) return
      if (msg.type === 'ready') {
        t0 = performance.now()
        onEvent({ type: 'streaming', streamId: msg.stream_id, t: 0 })
        sendAudio()
      } else if (msg.type === 'final') {
        finish({ type: 'done', msg })
      } else if (msg.type === 'error') {
        finish({ type: 'error', code: msg.code, message: msg.message })
      } else {
        onEvent({ type: 'server', msg, t: t() })
      }
    }

    onEvent({ type: 'connecting', t: 0 })
    signal?.addEventListener('abort', () => finish({ type: 'cancelled' }))

    open(url, {
      onMessage: handle,
      onClose: () => finish({
        type: 'error', code: 'connection_lost',
        message: 'Connection to the server closed before the transcription finished.',
      }),
    }).then((c) => {
      conn = c
      if (finished) return c.close()
      conn.sendJson({
        type: 'start', language, sample_rate: wav.sampleRate, channels: wav.channels, chunk_ms: chunkMs,
      })
    }).catch((err) => finish({ type: 'error', code: 'connect_failed', message: err.message }))
  })
}
