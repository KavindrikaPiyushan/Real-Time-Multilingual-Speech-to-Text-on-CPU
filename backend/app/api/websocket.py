"""WebSocket endpoint: one connection = one audio stream = one call leg.

Protocol (JSON text frames and binary frames)
  client -> {"type":"start","language":"English|Chinese|Indonesian|auto","sample_rate":16000,
             "channels":1,"chunk_ms":2000}
  server -> {"type":"ready","stream_id":...}
  client -> binary frames: raw 16-bit little-endian mono PCM at 16 kHz
  server -> {"type":"status","state":"receiving","audio_seconds":..,"chunks":..}   after each frame
  server -> {"type":"partial","text":...,<timings>}      transcript so far (may still change)
  client -> {"type":"end"}
  server -> {"type":"final","text":...,<latency, RTF, CPU, RAM>}
  server -> {"type":"error","code":...,"message":...} then closes, on any problem
"""
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState

from ..core.config import settings
from ..services.asr_service import ASRError
from ..services.stream_session import ProtocolError, StreamSession
from ..services.stream_transcriber import StreamTranscriber

log = logging.getLogger("asr.ws")
router = APIRouter()

# WebSocket close codes
CLOSE_NORMAL, CLOSE_POLICY, CLOSE_TOO_BUSY, CLOSE_INTERNAL = 1000, 1008, 1013, 1011


class Sender:
    """Serialises sends: the receive loop and the transcription task both write to the socket."""

    def __init__(self, ws: WebSocket):
        self.ws, self.lock = ws, asyncio.Lock()

    async def json(self, obj: dict) -> None:
        async with self.lock:
            if self.ws.application_state == WebSocketState.CONNECTED:
                await self.ws.send_json(obj)

    async def error(self, code: str, message: str, close_code: int = CLOSE_POLICY) -> None:
        """Best effort: tell the client what went wrong, then close."""
        try:
            await self.json({"type": "error", "code": code, "message": message})
            if self.ws.application_state == WebSocketState.CONNECTED:
                await self.ws.close(code=close_code)
        except Exception:  # the client may already be gone
            pass


async def read_json(message: dict) -> dict:
    if message.get("text") is None:
        raise ProtocolError("bad_message", "Expected a JSON text message.")
    try:
        obj = json.loads(message["text"])
    except json.JSONDecodeError:
        raise ProtocolError("bad_json", "Message is not valid JSON.")
    if not isinstance(obj, dict):
        raise ProtocolError("bad_json", "Message must be a JSON object.")
    return obj


async def run_transcriber(transcriber: StreamTranscriber, out: Sender, stream_id: str) -> None:
    """Runs the transcription loop; a model failure is reported to the client, not raised."""
    try:
        await transcriber.run()
    except ASRError as exc:
        log.error("stream %s ASR failure: %s", stream_id, exc)
        await out.error("asr_failed", "Speech recognition failed on the server.", CLOSE_INTERNAL)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("stream %s transcription task crashed", stream_id)
        await out.error("internal_error", "Internal server error.", CLOSE_INTERNAL)


@router.websocket("/ws/stream")
async def stream(ws: WebSocket):
    app = ws.app
    streams: dict = app.state.streams
    out = Sender(ws)
    await ws.accept()
    session: StreamSession | None = None
    task: asyncio.Task | None = None
    try:
        if len(streams) >= settings.max_streams:
            await out.error("server_busy", "Too many active streams. Try again later.", CLOSE_TOO_BUSY)
            return
        if not app.state.asr.loaded:
            await out.error("model_unavailable", "Speech model is not loaded on the server.", CLOSE_INTERNAL)
            return

        # 1. handshake: the first message must be 'start'
        try:
            first = await asyncio.wait_for(ws.receive(), timeout=settings.start_timeout_s)
        except asyncio.TimeoutError:
            await out.error("start_timeout", "No 'start' message received in time.")
            return
        if first["type"] == "websocket.disconnect":
            return
        session = StreamSession.from_start_message(
            await read_json(first), settings.languages, settings.max_stream_seconds)
        streams[session.stream_id] = session
        transcriber = StreamTranscriber(
            session, app.state.asr, app.state.infer_slots, out.json,
            settings.update_interval_s, settings.max_segment_s, settings.min_audio_s)
        await out.json({"type": "ready", "stream_id": session.stream_id})
        log.info("stream %s started (language=%s chunk_ms=%s, active=%d)",
                 session.stream_id, session.language or "auto", session.chunk_ms, len(streams))
        task = asyncio.create_task(run_transcriber(transcriber, out, session.stream_id))

        # 2. receive audio until 'end'
        while True:
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                log.info("stream %s disconnected after %.1fs of audio", session.stream_id, session.audio_seconds)
                return
            if message.get("bytes") is not None:
                total = session.add_pcm(message["bytes"])
                transcriber.notify()
                await out.json({"type": "status", "state": "receiving",
                                "audio_seconds": round(total, 2), "chunks": session.chunks_received})
            else:
                msg = await read_json(message)
                if msg.get("type") == "end":
                    break
                raise ProtocolError("unknown_message", f"Unknown message type {msg.get('type')!r}.")

        # 3. end of stream: let the transcriber finish (sends the final message)
        if session.samples_received == 0:
            raise ProtocolError("no_audio", "Stream ended without any audio.")
        transcriber.finish()
        await task
        if ws.application_state == WebSocketState.CONNECTED:
            await ws.close(code=CLOSE_NORMAL)
        log.info("stream %s finished: %.1fs audio, %d inferences", session.stream_id,
                 session.audio_seconds, transcriber.metrics.inferences)

    except ProtocolError as exc:
        log.warning("stream %s protocol error: %s", getattr(session, "stream_id", "-"), exc)
        await out.error(exc.code, str(exc))
    except WebSocketDisconnect:
        log.info("stream %s disconnected", getattr(session, "stream_id", "-"))
    except Exception:
        log.exception("stream %s crashed", getattr(session, "stream_id", "-"))
        await out.error("internal_error", "Internal server error.", CLOSE_INTERNAL)
    finally:
        if task is not None and not task.done():
            task.cancel()    # a model call already running in a worker thread will finish, its result is dropped
        if session is not None:
            streams.pop(session.stream_id, None)
