"""WebSocket protocol tests (no ASR needed). Start the backend first, then:
    python tests/test_ws_protocol.py [ws://localhost:8000/ws/stream]
"""
import asyncio
import json
import sys
import urllib.request
from pathlib import Path

import soundfile as sf
import websockets

URL = sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8000/ws/stream"
HTTP = URL.replace("ws://", "http://").split("/ws/")[0]
SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "english.wav"
START = {"type": "start", "language": "English", "sample_rate": 16000, "channels": 1, "chunk_ms": 2000}
results = []


def pcm_bytes() -> bytes:
    data, sr = sf.read(SAMPLE, dtype="int16")
    assert sr == 16000 and data.ndim == 1
    return data.tobytes()


def active_streams() -> int:
    with urllib.request.urlopen(f"{HTTP}/api/health") as r:
        return json.load(r)["active_streams"]


async def expect_error(name, messages, code):
    """Send messages (dict -> JSON text, bytes -> binary) and expect an error with `code`."""
    async with websockets.connect(URL) as ws:
        for m in messages:
            await ws.send(json.dumps(m) if isinstance(m, dict) else m)
        msg = None
        while msg is None or msg.get("type") not in ("error", "final"):
            msg = json.loads(await asyncio.wait_for(ws.recv(), 90))
    ok = msg.get("type") == "error" and msg.get("code") == code
    results.append((name, ok, msg))


async def main():
    pcm = pcm_bytes()
    size = 64_000  # 2 s chunks

    # happy path: start, chunks, end -> ready ... done
    async with websockets.connect(URL) as ws:
        await ws.send(json.dumps(START))
        ready = json.loads(await ws.recv())
        for i in range(0, len(pcm), size):
            await ws.send(pcm[i:i + size])
        await ws.send(json.dumps({"type": "end"}))
        msgs = []
        while True:
            m = json.loads(await asyncio.wait_for(ws.recv(), 90))
            msgs.append(m)
            if m["type"] in ("final", "error"):
                break
    status = [m for m in msgs if m["type"] == "status"]
    done = msgs[-1]
    ok = (ready["type"] == "ready" and done["type"] == "final" and len(status) == 6
          and abs(done["audio_seconds"] - 11.1) < 0.05)
    ok = ok and "family" in done["text"]
    results.append(("happy path (6 chunks, 11.1 s, transcript present)", ok, done))

    # a chunk split in the middle of a 16-bit sample must not corrupt the audio
    async with websockets.connect(URL) as ws:
        await ws.send(json.dumps(START)); await ws.recv()
        await ws.send(pcm[:1001]); await ws.send(pcm[1001:5000])
        await ws.send(json.dumps({"type": "end"}))
        while True:
            m = json.loads(await asyncio.wait_for(ws.recv(), 90))
            if m["type"] in ("final", "error"):
                break
    results.append(("odd-sized frames handled", m["type"] == "final" and abs(m["audio_seconds"] - 5000 / 2 / 16000) < 0.01, m))  # server rounds to 2 decimals

    await expect_error("wrong sample rate", [{**START, "sample_rate": 44100}], "bad_sample_rate")
    await expect_error("unsupported language", [{**START, "language": "French"}], "bad_language")
    await expect_error("stereo rejected", [{**START, "channels": 2}], "bad_channels")
    await expect_error("bad chunk_ms", [{**START, "chunk_ms": -5}], "bad_chunk_ms")
    await expect_error("audio before start", [pcm[:64000]], "bad_message")
    await expect_error("invalid JSON", ["not json"], "bad_json")
    await expect_error("first message not 'start'", [{"type": "end"}], "bad_start")
    await expect_error("unknown message type", [START, {"type": "dance"}], "unknown_message")
    await expect_error("end with no audio", [START, {"type": "end"}], "no_audio")

    # abrupt disconnect mid-stream: server must clean the stream up
    ws = await websockets.connect(URL)
    await ws.send(json.dumps(START)); await ws.recv()
    await ws.send(pcm[:64000]); await ws.recv()
    during = active_streams()
    await ws.close()
    await asyncio.sleep(0.5)
    after = active_streams()
    results.append(("disconnect cleans up stream", during == 1 and after == 0, {"during": during, "after": after}))

    failed = 0
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  -> {detail}"))
        failed += not ok
    print(f"\n{len(results) - failed}/{len(results)} passed")
    sys.exit(1 if failed else 0)


asyncio.run(main())
