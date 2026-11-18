"""WebSocket endpoint: one connection = one audio stream = one call leg.

Protocol (JSON text frames and binary frames)
  client -> {"type":"start","language":"English|Chinese|Indonesian|auto","sample_rate":16000,
             "channels":1,"chunk_ms":2000}
  server -> {"type":"ready","stream_id":...}
  client -> binary frames: raw 16-bit little-endian mono PCM at 16 kHz
  server -> {"type":"status","state":"receiving","audio_seconds":..,"chunks":..}   (Step 3 stub)
  client -> {"type":"end"}
  server -> {"type":"done",...}                                                     (Step 3 stub)
  server -> {"type":"error","code":...,"message":...} then closes, on any problem
"""
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState

from ..core.config import settings
from ..services.stream_session import ProtocolError, StreamSession

log = logging.getLogger("asr.ws")
router = APIRouter()

# WebSocket close codes
CLOSE_NORMAL, CLOSE_POLICY, CLOSE_TOO_BUSY, CLOSE_INTERNAL = 1000, 1008, 1013, 1011


async def send_error(ws: WebSocket, code: str, message: str, close_code: int = CLOSE_POLICY) -> None:
    """Best effort: tell the client what went wrong, then close."""
    if ws.application_state == WebSocketState.CONNECTED:
        try:
            await ws.send_json({"type": "error", "code": code, "message": message})
            await ws.close(code=close_code)
        except Exception:  # the client may already be gone
            pass


async def read_json(ws: WebSocket, message: dict) -> dict:
    if message.get("text") is None:
        raise ProtocolError("bad_message", "Expected a JSON text message.")
    try:
        obj = json.loads(message["text"])
    except json.JSONDecodeError:
        raise ProtocolError("bad_json", "Message is not valid JSON.")
    if not isinstance(obj, dict):
        raise ProtocolError("bad_json", "Message must be a JSON object.")
    return obj


@router.websocket("/ws/stream")
async def stream(ws: WebSocket):
    streams: dict = ws.app.state.streams
    await ws.accept()
    session: StreamSession | None = None
    try:
        if len(streams) >= settings.max_streams:
            await send_error(ws, "server_busy", "Too many active streams. Try again later.", CLOSE_TOO_BUSY)
            return

        # 1. handshake: the first message must be 'start'
        try:
            first = await asyncio.wait_for(ws.receive(), timeout=settings.start_timeout_s)
        except asyncio.TimeoutError:
            await send_error(ws, "start_timeout", "No 'start' message received in time.")
            return
        if first["type"] == "websocket.disconnect":
            return
        session = StreamSession.from_start_message(
            await read_json(ws, first), settings.languages, settings.max_stream_seconds)
        streams[session.stream_id] = session
        await ws.send_json({"type": "ready", "stream_id": session.stream_id})
        log.info("stream %s started (language=%s chunk_ms=%s, active=%d)",
                 session.stream_id, session.language or "auto", session.chunk_ms, len(streams))

        # 2. receive audio until 'end'
        while True:
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                log.info("stream %s disconnected after %.1fs of audio", session.stream_id, session.audio_seconds)
                return
            if message.get("bytes") is not None:
                total = session.add_pcm(message["bytes"])
                await ws.send_json({"type": "status", "state": "receiving",
                                    "audio_seconds": round(total, 2), "chunks": session.chunks_received})
            else:
                msg = await read_json(ws, message)
                if msg.get("type") == "end":
                    break
                raise ProtocolError("unknown_message", f"Unknown message type {msg.get('type')!r}.")

        # 3. end of stream (Step 4 will run the final transcription here)
        if session.samples_received == 0:
            raise ProtocolError("no_audio", "Stream ended without any audio.")
        await ws.send_json({"type": "done", "stream_id": session.stream_id,
                            "audio_seconds": round(session.audio_seconds, 2),
                            "chunks": session.chunks_received})
        await ws.close(code=CLOSE_NORMAL)

    except ProtocolError as exc:
        log.warning("stream %s protocol error: %s", getattr(session, "stream_id", "-"), exc)
        await send_error(ws, exc.code, str(exc))
    except WebSocketDisconnect:
        log.info("stream %s disconnected", getattr(session, "stream_id", "-"))
    except Exception:
        log.exception("stream %s crashed", getattr(session, "stream_id", "-"))
        await send_error(ws, "internal_error", "Internal server error.", CLOSE_INTERNAL)
    finally:
        if session is not None:
            streams.pop(session.stream_id, None)
