import { useCallback, useReducer, useRef } from 'react'
import { streamWav } from '../services/streamer.js'
import { parseWav, WavError } from '../services/wav.js'

export const initialState = {
  status: 'idle', // idle | reading | connecting | streaming | finishing | done | error | cancelled
  file: null,     // { name, durationS, sizeBytes }
  chunkMs: 2000,
  language: 'auto',
  sentSeconds: 0,
  receivedSeconds: 0,   // audio the server has acknowledged
  text: '',
  committed: '',
  detectedLanguage: null,
  updates: [],          // one row per partial transcript
  firstTextMs: null,    // stream start -> first text shown (client side)
  endSentMs: null,
  finalLatencyMs: null, // 'end' sent -> final transcript shown (client side)
  final: null,          // the server's final message (RTF, model time, CPU, RAM ...)
  error: null,          // { code, message }
}

export function reducer(state, action) {
  switch (action.type) {
    case 'reset':
      return { ...initialState }
    case 'reading':
      return { ...initialState, status: 'reading', chunkMs: action.chunkMs, language: action.language }
    case 'file':
      return { ...state, file: action.file }
    case 'fail':
      return { ...state, status: 'error', error: action.error }
    case 'event': {
      const e = action.event
      switch (e.type) {
        case 'connecting': return { ...state, status: 'connecting' }
        case 'streaming': return { ...state, status: 'streaming' }
        case 'sent': return { ...state, sentSeconds: e.sentSeconds }
        case 'ending': return { ...state, status: 'finishing', endSentMs: e.t }
        case 'server': {
          const m = e.msg
          if (m.type === 'status') return { ...state, receivedSeconds: m.audio_seconds }
          if (m.type === 'partial') {
            const update = {
              t: e.t, covered: m.audio_seconds_transcribed, received: m.audio_seconds_received,
              window: m.window_seconds, processing: m.processing_seconds,
            }
            return {
              ...state,
              text: m.text, committed: m.committed_text, detectedLanguage: m.language ?? state.detectedLanguage,
              updates: [...state.updates, update],
              firstTextMs: state.firstTextMs ?? (m.text ? e.t : null),
            }
          }
          return state
        }
        case 'done': {
          const m = e.msg
          return {
            ...state, status: 'done', final: m, text: m.text, committed: m.text,
            detectedLanguage: m.language ?? state.detectedLanguage,
            firstTextMs: state.firstTextMs ?? (m.text ? e.t : null),
            finalLatencyMs: state.endSentMs == null ? null : e.t - state.endSentMs,
          }
        }
        case 'error': return { ...state, status: 'error', error: { code: e.code, message: e.message } }
        case 'cancelled': return { ...state, status: 'cancelled' }
        default: return state
      }
    }
    default:
      return state
  }
}

export function useAudioStreaming() {
  const [state, dispatch] = useReducer(reducer, initialState)
  const abortRef = useRef(null)

  const start = useCallback(async (file, { language = 'auto', chunkMs = 2000 } = {}) => {
    abortRef.current?.abort()
    dispatch({ type: 'reading', chunkMs, language })
    let wav
    try {
      wav = parseWav(await file.arrayBuffer())
    } catch (err) {
      const message = err instanceof WavError ? err.message : `Could not read the file: ${err.message}`
      dispatch({ type: 'fail', error: { code: 'invalid_audio', message } })
      return
    }
    dispatch({ type: 'file', file: { name: file.name, durationS: wav.durationS, sizeBytes: file.size } })
    const controller = new AbortController()
    abortRef.current = controller
    await streamWav({
      wav, language, chunkMs, signal: controller.signal,
      onEvent: (event) => dispatch({ type: 'event', event }),
    })
  }, [])

  const cancel = useCallback(() => abortRef.current?.abort(), [])
  const reset = useCallback(() => {
    abortRef.current?.abort()
    dispatch({ type: 'reset' })
  }, [])

  return { state, start, cancel, reset }
}
