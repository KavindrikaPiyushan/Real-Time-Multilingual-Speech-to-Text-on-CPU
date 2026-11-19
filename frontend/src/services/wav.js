// Minimal WAV (RIFF) reader. We parse the header ourselves instead of using the browser's
// decodeAudioData(), because that silently resamples and converts the audio, and we want to
// verify the file really is 16 kHz mono 16-bit Linear PCM before streaming it.

export const REQUIRED = { sampleRate: 16000, channels: 1, bitsPerSample: 16 }

export class WavError extends Error {}

const FORMAT_PCM = 1
const FORMAT_EXTENSIBLE = 0xfffe

const tag = (view, offset) =>
  String.fromCharCode(
    view.getUint8(offset), view.getUint8(offset + 1),
    view.getUint8(offset + 2), view.getUint8(offset + 3),
  )

/** Parse a WAV file. Returns the format and a view of the raw PCM bytes, or throws WavError. */
export function parseWav(arrayBuffer) {
  const view = new DataView(arrayBuffer)
  if (view.byteLength < 44 || tag(view, 0) !== 'RIFF' || tag(view, 8) !== 'WAVE') {
    throw new WavError('This is not a WAV file.')
  }

  let fmt = null
  let data = null
  let pos = 12
  while (pos + 8 <= view.byteLength) {
    const id = tag(view, pos)
    const size = view.getUint32(pos + 4, true)
    const body = pos + 8
    if (id === 'fmt ') {
      let formatCode = view.getUint16(body, true)
      if (formatCode === FORMAT_EXTENSIBLE && size >= 26) formatCode = view.getUint16(body + 24, true)
      fmt = {
        formatCode,
        channels: view.getUint16(body + 2, true),
        sampleRate: view.getUint32(body + 4, true),
        bitsPerSample: view.getUint16(body + 14, true),
      }
    } else if (id === 'data') {
      // Some writers leave a wrong/huge size; never read past the end of the file.
      data = { offset: body, size: Math.min(size, view.byteLength - body) }
      break
    }
    pos = body + size + (size & 1) // chunks are padded to an even size
  }

  if (!fmt) throw new WavError('WAV header is missing the format chunk.')
  if (!data || data.size === 0) throw new WavError('WAV file contains no audio data.')
  if (fmt.formatCode !== FORMAT_PCM) {
    throw new WavError('Audio is not Linear PCM (it may be compressed). Please convert it to PCM WAV.')
  }

  const problems = []
  if (fmt.sampleRate !== REQUIRED.sampleRate) problems.push(`${fmt.sampleRate} Hz instead of 16000 Hz`)
  if (fmt.channels !== REQUIRED.channels) problems.push(`${fmt.channels} channels instead of mono`)
  if (fmt.bitsPerSample !== REQUIRED.bitsPerSample) problems.push(`${fmt.bitsPerSample}-bit instead of 16-bit`)
  if (problems.length) {
    throw new WavError(
      `Unsupported audio: ${problems.join(', ')}. Convert it with: ` +
      'ffmpeg -i input.wav -ar 16000 -ac 1 -c:a pcm_s16le output.wav',
    )
  }

  const bytesPerSecond = fmt.sampleRate * fmt.channels * (fmt.bitsPerSample / 8)
  const size = data.size - (data.size % 2) // whole samples only
  return {
    ...fmt,
    bytesPerSecond,
    durationS: size / bytesPerSecond,
    // little-endian 16-bit samples: exactly what the backend expects, so no conversion needed
    pcm: new Uint8Array(arrayBuffer, data.offset, size),
  }
}

/** Split PCM bytes into chunks of chunkMs. The last chunk is whatever is left (usually shorter). */
export function chunkBounds(totalBytes, bytesPerSecond, chunkMs) {
  const chunkBytes = Math.max(2, Math.round((bytesPerSecond * chunkMs) / 1000 / 2) * 2)
  const bounds = []
  for (let start = 0; start < totalBytes; start += chunkBytes) {
    bounds.push([start, Math.min(start + chunkBytes, totalBytes)])
  }
  return bounds
}
