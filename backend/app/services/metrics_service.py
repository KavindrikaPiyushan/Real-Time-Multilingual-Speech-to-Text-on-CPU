"""Measurements: per-stream inference stats and process/system snapshots."""
from __future__ import annotations

from dataclasses import dataclass

import psutil

_process = psutil.Process()
_process.cpu_percent(None)   # prime the counter so the first real reading is meaningful
psutil.cpu_percent(None)


@dataclass
class StreamMetrics:
    inferences: int = 0
    total_infer_s: float = 0.0     # time the model spent computing for this stream
    total_queue_s: float = 0.0     # time spent waiting for a free inference slot
    first_text_latency_s: float | None = None        # first audio chunk -> first non-empty transcript
    audio_s_at_first_text: float | None = None       # how much audio had arrived at that moment

    def record(self, infer_s: float, queue_s: float) -> None:
        self.inferences += 1
        self.total_infer_s += infer_s
        self.total_queue_s += queue_s

    def mark_text(self, latency_s: float, audio_s: float) -> None:
        if self.first_text_latency_s is None:
            self.first_text_latency_s = latency_s
            self.audio_s_at_first_text = audio_s


def system_snapshot() -> dict:
    """CPU and memory right now. Process CPU can exceed 100% (one full core = 100%)."""
    return {
        "system_cpu_percent": psutil.cpu_percent(None),
        "process_cpu_percent": _process.cpu_percent(None),
        "process_rss_mb": round(_process.memory_info().rss / 1e6),
    }
