// Failure scenarios with REAL servers started and killed by this script (uses ports 8003/8004).
//   node tests/failure_check.mjs
import { spawn, execSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const imp = (p) => import(`file:///${path.join(root, 'frontend', 'src', p).replaceAll('\\', '/')}`)
const { parseWav } = await imp('services/wav.js')
const { streamWav } = await imp('services/streamer.js')

const b = readFileSync(path.join(root, 'samples', 'english.wav'))
const wav = parseWav(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength))
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const results = []
const check = (name, ok, detail = '') => { results.push(ok); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${ok ? '' : '  -> ' + detail}`) }

function startServer(port, env = {}) {
  const py = path.join(root, 'backend', '.venv', 'Scripts', 'python.exe')
  const p = spawn(py, ['-m', 'uvicorn', 'app.main:app', '--port', String(port)], {
    cwd: path.join(root, 'backend'), env: { ...process.env, PYTHONUTF8: '1', TQDM_DISABLE: '1', ...env }, stdio: 'ignore',
  })
  return p
}
const kill = (p) => { try { execSync(`taskkill /F /T /PID ${p.pid}`, { stdio: 'ignore' }) } catch { /* gone */ } }
async function waitHealth(port, tries = 60) {
  for (let i = 0; i < tries; i++) {
    try { return await (await fetch(`http://localhost:${port}/api/health`)).json() } catch { await sleep(1000) }
  }
  throw new Error('server did not start')
}

// 1. the server process dies in the middle of a stream
let srv = startServer(8003)
let h = await waitHealth(8003)
check('server healthy before the crash test', h.model_loaded === true, JSON.stringify(h))
setTimeout(() => kill(srv), 5000)
let last = await streamWav({ wav, language: 'English', chunkMs: 2000, url: 'ws://localhost:8003/ws/stream' })
check('server killed mid-stream -> client gets connection_lost', last.type === 'error' && last.code === 'connection_lost', JSON.stringify(last))
kill(srv)

// 2. the model cannot be loaded (bad model id): server stays up and says so
srv = startServer(8004, { ASR_MODEL_ID: 'does-not-exist/none', HF_HUB_OFFLINE: '1' })
h = await waitHealth(8004)
check('health reports model not loaded + error text', h.model_loaded === false && !!h.error, JSON.stringify(h))
last = await streamWav({ wav, language: 'English', chunkMs: 2000, url: 'ws://localhost:8004/ws/stream' })
check('stream refused cleanly with model_unavailable', last.type === 'error' && last.code === 'model_unavailable', JSON.stringify(last))
const form = new FormData()
form.append('file', new Blob([b]), 'english.wav')
const res = await fetch('http://localhost:8004/api/transcribe', { method: 'POST', body: form })
check('REST transcribe without model -> HTTP 503', res.status === 503, String(res.status))
kill(srv)

console.log(`\n${results.filter(Boolean).length}/${results.length} passed`)
process.exit(results.every(Boolean) ? 0 : 1)
