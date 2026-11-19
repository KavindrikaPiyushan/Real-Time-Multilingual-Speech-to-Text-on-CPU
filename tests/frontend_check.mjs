// Runs the frontend's real logic (WAV parser, streamer, reducer) in Node against the live backend.
//   node tests/frontend_check.mjs        (backend must be running on :8000)
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const src = (p) => import(`file:///${path.join(root, 'frontend', 'src', p).replaceAll('\\', '/')}`)
const { parseWav, WavError, chunkBounds } = await src('services/wav.js')
const { streamWav } = await src('services/streamer.js')
const { reducer, initialState } = await src('hooks/useAudioStreaming.js').catch(() => ({}))

const load = (rel) => {
  const b = readFileSync(path.join(root, rel))
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength)
}
const results = []
const check = (name, ok, detail = '') => { results.push(ok); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${ok ? '' : '  -> ' + detail}`) }
const throwsWav = (fn) => { try { fn(); return null } catch (e) { return e instanceof WavError ? e.message : `wrong error: ${e}` } }

// --- WAV parsing -------------------------------------------------------------------
const en = parseWav(load('samples/english.wav'))
check('parse 16 kHz mono WAV', en.sampleRate === 16000 && en.channels === 1 && Math.abs(en.durationS - 11.1) < 0.05, JSON.stringify({ ...en, pcm: en.pcm.length }))
const stereo = throwsWav(() => parseWav(load('docs/wav/Recording.wav')))
check('reject stereo WAV with a helpful message', stereo?.includes('2 channels') && stereo.includes('ffmpeg'), stereo)
const hi = throwsWav(() => parseWav(load('docs/wav/Mandarin.wav')))
check('reject 44.1 kHz WAV', hi?.includes('44100 Hz'), hi)
check('reject non-WAV file', throwsWav(() => parseWav(load('reports/phase2_findings.md'))) === 'This is not a WAV file.')
check('reject truncated header', throwsWav(() => parseWav(new ArrayBuffer(10))) === 'This is not a WAV file.')
const b = chunkBounds(en.pcm.length, en.bytesPerSecond, 2000)
check('chunking: 2 s chunks, short last chunk', b.length === 6 && b[0][1] - b[0][0] === 64000 && b.at(-1)[1] === en.pcm.length && b.every(([s, e]) => (e - s) % 2 === 0), JSON.stringify(b))

// --- streaming against the backend, reduced the same way the React hook does --------
async function run(file, language, chunkMs, opts = {}) {
  const wav = parseWav(load(file))
  let state = reducer ? { ...initialState, file: { durationS: wav.durationS } } : null
  const last = await streamWav({
    wav, language, chunkMs, ...opts,
    onEvent: (event) => { if (state) state = reducer(state, { type: 'event', event }) },
  })
  return { last, state }
}

let r = await run('samples/english.wav', 'English', 2000)
check('stream English: done with transcript', r.last.type === 'done' && /family/i.test(r.last.msg.text), JSON.stringify(r.last).slice(0, 300))
check('reducer: status, first-text and final latency recorded',
  r.state.status === 'done' && r.state.firstTextMs > 0 && r.state.finalLatencyMs >= 0 && r.state.updates.length >= 2,
  JSON.stringify({ ...r.state, text: '' }).slice(0, 400))
console.log(`      first text ${r.state.firstTextMs} ms | final after end ${r.state.finalLatencyMs} ms | ${r.state.updates.length} updates | ${r.state.text}`)

r = await run('samples/mandarin.wav', 'auto', 2000)
check('stream Mandarin with auto-detect', r.last.type === 'done' && r.last.msg.text.includes('你叫什么名字'), r.last.msg?.text ?? JSON.stringify(r.last))

// error handling: nothing listening, and a server that closes the connection mid-stream
r = await run('samples/english.wav', 'English', 2000, { url: 'ws://localhost:9/ws/stream' })
check('backend unreachable -> clean error', r.last.type === 'error' && r.last.code === 'connect_failed' && r.state.status === 'error', JSON.stringify(r.last))

r = await run('samples/english.wav', 'French', 2000)
check('server rejects bad language -> error shown', r.last.type === 'error' && r.last.code === 'bad_language', JSON.stringify(r.last))

const ctl = new AbortController()
setTimeout(() => ctl.abort(), 3000)
r = await run('samples/english.wav', 'English', 2000, { signal: ctl.signal })
check('user stop -> cancelled', r.last.type === 'cancelled' && r.state.status === 'cancelled', JSON.stringify(r.last))
await new Promise((res) => setTimeout(res, 800))
const health = await (await fetch('http://localhost:8000/api/health')).json()
check('server cleaned up the cancelled stream', health.active_streams === 0, JSON.stringify(health))

console.log(`\n${results.filter(Boolean).length}/${results.length} passed`)
process.exit(results.every(Boolean) ? 0 : 1)
