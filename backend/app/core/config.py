"""Central configuration. Every value can be overridden with an environment variable."""
import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


@dataclass(frozen=True)
class Settings:
    model_id: str = os.environ.get("ASR_MODEL_ID", "Qwen/Qwen3-ASR-0.6B-hf")
    sample_rate: int = 16_000
    # How many model inferences may run at the same time. Torch already uses all
    # cores for one inference, so more than 1 usually just causes contention.
    max_concurrent_inferences: int = _int("ASR_MAX_CONCURRENT_INFERENCES", 1)
    torch_threads: int = _int("ASR_TORCH_THREADS", 0)          # 0 = torch default
    max_upload_mb: int = _int("ASR_MAX_UPLOAD_MB", 50)
    max_streams: int = _int("ASR_MAX_STREAMS", 20)              # simultaneous WebSocket streams
    max_stream_seconds: int = _int("ASR_MAX_STREAM_SECONDS", 600)  # audio cap per stream
    start_timeout_s: int = _int("ASR_START_TIMEOUT_S", 10)      # time allowed to send the 'start' message
    # Streaming transcription (application-level streaming, see stream_transcriber.py)
    update_interval_s: float = _float("ASR_UPDATE_INTERVAL_S", 2.0)  # new audio needed before the next partial
    max_segment_s: float = _float("ASR_MAX_SEGMENT_S", 10.0)         # a segment is committed once it reaches this
    min_audio_s: float = _float("ASR_MIN_AUDIO_S", 1.0)              # do not transcribe less audio than this
    # Languages offered in the UI. None = auto-detect.
    languages: tuple[str, ...] = ("English", "Chinese", "Indonesian")
    cors_origins: tuple[str, ...] = tuple(
        os.environ.get("ASR_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","))


settings = Settings()
