// WebSocket + HTTP endpoints and a tiny stream connection helper.

export const API_URL = (import.meta.env?.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')
export const WS_URL = API_URL.replace(/^http/, 'ws') + '/ws/stream'

export async function fetchHealth(apiUrl = API_URL) {
  const res = await fetch(`${apiUrl}/api/health`)
  if (!res.ok) throw new Error(`Health check failed (HTTP ${res.status})`)
  return res.json()
}

/**
 * Open a stream connection. Resolves once the socket is open; rejects if it cannot connect.
 * handlers: { onMessage(obj), onClose({code, reason, wasClean}) }
 */
export function openStream(url, { onMessage, onClose }) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(url)
    ws.binaryType = 'arraybuffer'
    let opened = false
    ws.onopen = () => {
      opened = true
      resolve({
        sendJson: (obj) => ws.send(JSON.stringify(obj)),
        sendBinary: (bytes) => ws.send(bytes),
        close: () => ws.close(1000),
        get open() { return ws.readyState === WebSocket.OPEN },
        get buffered() { return ws.bufferedAmount },
      })
    }
    ws.onmessage = (ev) => {
      try {
        onMessage(JSON.parse(ev.data))
      } catch {
        /* ignore anything that is not JSON */
      }
    }
    ws.onerror = () => {
      if (!opened) reject(new Error(`Cannot connect to the backend at ${url}. Is it running?`))
    }
    ws.onclose = (ev) => {
      if (!opened) reject(new Error(`Cannot connect to the backend at ${url}. Is it running?`))
      else onClose({ code: ev.code, reason: ev.reason, wasClean: ev.wasClean })
    }
  })
}
