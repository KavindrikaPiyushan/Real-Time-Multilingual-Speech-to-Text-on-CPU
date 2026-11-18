"""Streams a WAV file to the backend like a live call (chunks paced at real-time speed).

    python tests/stream_client.py samples/english.wav --language English --chunk-ms 2000
Prints every partial transcript with client-side timings and the final summary.
Also importable: stream_file() is reused by the load test.
"""
import argparse
import asyncio
import json
import time

import soundfile as sf
import websockets

URL = "ws://localhost:8000/ws/stream"


async def stream_file(path: str, language: str = "auto", chunk_ms: int = 2000, pace: bool = True,
                      url: str = URL, verbose: bool = False) -> dict:
    """Stream one file. Returns client-side measurements plus the server's final message."""
    data, sr = sf.read(path, dtype="int16")
    assert sr == 16000 and data.ndim == 1, "need a 16 kHz mono WAV"
    pcm = data.tobytes()
    size = int(16000 * 2 * chunk_ms / 1000)
    out = {"file": path, "partials": [], "error": None}
    async with websockets.connect(url, max_size=None) as ws:
        await ws.send(json.dumps({"type": "start", "language": language, "sample_rate": 16000,
                                  "channels": 1, "chunk_ms": chunk_ms}))
        ready = json.loads(await ws.recv())
        if ready["type"] != "ready":
            out["error"] = ready
            return out
        t0 = time.perf_counter()
        sent_all = asyncio.Event()
        end_sent = {}

        async def sender():
            for i in range(0, len(pcm), size):
                chunk = pcm[i:i + size]
                if pace:   # a live call only has this audio once it has been spoken: wait for its end
                    await asyncio.sleep(max(0, t0 + (i + len(chunk)) / 32000 - time.perf_counter()))
                await ws.send(chunk)
            end_sent["t"] = time.perf_counter()
            await ws.send(json.dumps({"type": "end"}))
            sent_all.set()

        send_task = asyncio.create_task(sender())
        async for raw in ws:
            m = json.loads(raw)
            now = time.perf_counter() - t0
            if m["type"] == "partial":
                out["partials"].append({"t": round(now, 2), **m})
                if m["text"] and "first_text_client_s" not in out:
                    out["first_text_client_s"] = round(now, 2)
                if verbose:
                    print(f"[{now:6.2f}s] partial (audio {m['audio_seconds_transcribed']:.1f}s, "
                          f"took {m['processing_seconds']:.1f}s): {m['text']}")
            elif m["type"] == "final":
                out["final"] = m
                out["final_client_latency_s"] = round(time.perf_counter() - end_sent["t"], 2)
                out["total_wall_s"] = round(now, 2)
            elif m["type"] == "error":
                out["error"] = m
                break
        await send_task
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("--language", default="auto")
    ap.add_argument("--chunk-ms", type=int, default=2000)
    ap.add_argument("--no-pace", action="store_true", help="send as fast as possible")
    a = ap.parse_args()
    r = asyncio.run(stream_file(a.wav, a.language, a.chunk_ms, not a.no_pace, verbose=True))
    if r["error"]:
        print("ERROR:", r["error"])
    else:
        f = r["final"]
        print("\nFINAL:", f["text"])
        print(f"audio {f['audio_seconds']}s | first text {r.get('first_text_client_s')}s after stream start (client) | "
              f"final latency {r['final_client_latency_s']}s after 'end' | inferences {f['inferences']} | "
              f"model time {f['total_inference_seconds']}s | RTF {f['rtf']} | RAM {f['process_rss_mb']} MB")
