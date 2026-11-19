"""State of one audio stream (= one call leg). No web or model code in here."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

import numpy as np

from .audio_service import AudioError, pcm16_bytes_to_float32

SUPPORTED_SAMPLE_RATE = 16_000


class ProtocolError(ValueError):
    """The client broke the streaming protocol. `code` is sent to the client."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class StreamSession:
    language: str | None                     # None = auto-detect
    sample_rate: int = SUPPORTED_SAMPLE_RATE
    chunk_ms: int | None = None              # label only, used for metrics
    max_seconds: int = 600
    stream_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    created_at: float = field(default_factory=time.perf_counter)
    first_chunk_at: float | None = None
    chunks_received: int = 0
    bytes_received: int = 0
    _pending_byte: bytes = b""               # carries a split sample between chunks
    _blocks: list = field(default_factory=list)
    _audio_cache: np.ndarray | None = None

    @classmethod
    def from_start_message(cls, msg: dict, allowed_languages, max_seconds: int) -> "StreamSession":
        """Validate the client's 'start' message and create the session."""
        if msg.get("type") != "start":
            raise ProtocolError("bad_start", "First message must be a JSON object with type 'start'.")
        language = msg.get("language", "auto")
        if language in (None, "", "auto"):
            language = None
        elif language not in allowed_languages:
            raise ProtocolError("bad_language", f"Unsupported language '{language}'. "
                                f"Use one of: auto, {', '.join(allowed_languages)}.")
        if msg.get("sample_rate") != SUPPORTED_SAMPLE_RATE:
            raise ProtocolError("bad_sample_rate", f"Only {SUPPORTED_SAMPLE_RATE} Hz audio is supported, "
                                f"got {msg.get('sample_rate')!r}.")
        if msg.get("channels", 1) != 1:
            raise ProtocolError("bad_channels", "Only mono audio is supported.")
        chunk_ms = msg.get("chunk_ms")
        if chunk_ms is not None and not (isinstance(chunk_ms, int) and 10 <= chunk_ms <= 60_000):
            raise ProtocolError("bad_chunk_ms", "chunk_ms must be an integer between 10 and 60000.")
        return cls(language=language, chunk_ms=chunk_ms, max_seconds=max_seconds)

    @property
    def samples_received(self) -> int:
        return self.bytes_received // 2

    @property
    def audio_seconds(self) -> float:
        return self.samples_received / self.sample_rate

    def add_pcm(self, raw: bytes) -> float:
        """Append a binary frame of 16-bit little-endian PCM. Returns total audio seconds so far."""
        if not raw:
            raise ProtocolError("empty_chunk", "Received an empty audio frame.")
        if self.first_chunk_at is None:
            self.first_chunk_at = time.perf_counter()
        data = self._pending_byte + raw
        usable = len(data) - (len(data) % 2)          # keep whole samples only
        self._pending_byte = data[usable:]
        if usable:
            try:
                self._blocks.append(pcm16_bytes_to_float32(data[:usable]))
            except AudioError as exc:
                raise ProtocolError("bad_audio", str(exc)) from exc
            self._audio_cache = None
        self.bytes_received += usable
        self.chunks_received += 1
        if self.audio_seconds > self.max_seconds:
            raise ProtocolError("stream_too_long", f"Stream exceeds the {self.max_seconds} s limit.")
        return self.audio_seconds

    def audio(self) -> np.ndarray:
        """All audio received so far as float32 mono."""
        if self._audio_cache is None:
            self._audio_cache = (np.concatenate(self._blocks) if self._blocks
                                 else np.zeros(0, dtype=np.float32))
            self._blocks = [self._audio_cache] if self._audio_cache.size else []
        return self._audio_cache

    def elapsed_since_first_chunk(self) -> float:
        return 0.0 if self.first_chunk_at is None else time.perf_counter() - self.first_chunk_at
