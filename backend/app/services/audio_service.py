"""Audio validation and loading. Knows nothing about the ASR model or the web layer."""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import soundfile as sf
import soxr

TARGET_SR = 16_000


class AudioError(ValueError):
    """The audio is invalid or unsupported. The message is safe to show to a user."""


@dataclass
class AudioInfo:
    sample_rate: int
    channels: int
    subtype: str          # e.g. PCM_16
    duration_s: float
    notes: list[str] = field(default_factory=list)   # conversions applied

    @property
    def is_preferred_format(self) -> bool:
        return self.sample_rate == TARGET_SR and self.channels == 1 and self.subtype == "PCM_16"


def load_wav(source: str | Path | bytes, strict: bool = False) -> tuple[np.ndarray, AudioInfo]:
    """Read a WAV file (path or bytes) and return (float32 mono 16 kHz samples, info).

    strict=True: reject anything that is not 16 kHz mono (the assignment's preferred format).
    strict=False: downmix to mono and resample to 16 kHz, and record what was done in info.notes.
    """
    try:
        handle = io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else str(source)
        with sf.SoundFile(handle) as f:
            if f.format != "WAV":
                raise AudioError(f"Not a WAV file (format: {f.format}).")
            sr, channels, subtype = f.samplerate, f.channels, f.subtype
            if not subtype.startswith(("PCM", "FLOAT")):
                raise AudioError(f"Unsupported WAV encoding: {subtype}. Expected Linear PCM.")
            data = f.read(dtype="float32", always_2d=True)
    except AudioError:
        raise
    except Exception as exc:  # soundfile raises LibsndfileError / RuntimeError for bad files
        raise AudioError(f"Could not read audio: {exc}") from exc

    if data.shape[0] == 0:
        raise AudioError("Audio file is empty.")

    info = AudioInfo(sample_rate=sr, channels=channels, subtype=subtype, duration_s=data.shape[0] / sr)

    if strict and (sr != TARGET_SR or channels != 1):
        raise AudioError(f"Expected 16 kHz mono WAV, got {sr} Hz and {channels} channel(s).")

    if channels > 1:
        data = data.mean(axis=1, keepdims=True)
        info.notes.append(f"downmixed {channels} channels to mono")
    audio = data[:, 0]

    if sr != TARGET_SR:
        audio = soxr.resample(audio, sr, TARGET_SR)
        info.notes.append(f"resampled {sr} Hz to {TARGET_SR} Hz")

    return np.ascontiguousarray(audio, dtype=np.float32), info


def pcm16_bytes_to_float32(raw: bytes) -> np.ndarray:
    """Convert raw little-endian 16-bit PCM bytes (e.g. a WebSocket chunk) to float32 in [-1, 1]."""
    if len(raw) % 2:
        raise AudioError("PCM16 data must contain an even number of bytes.")
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
