"""Application-level streaming transcription for one stream.

Qwen3-ASR's Transformers backend is offline-only, so "streaming" is simulated:
  * audio chunks accumulate in the StreamSession;
  * whenever enough new audio has arrived, the CURRENT SEGMENT (everything since the last
    committed cut) is transcribed again and sent as a `partial` (text may still change);
  * when the segment reaches max_segment_s it is cut at the quietest moment near its end and
    its text is committed permanently, so the cost per update stays bounded;
  * on `end`, whatever is left is transcribed and a `final` message is sent.
The audio chunk size (how data is sent) is independent of this processing window.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable

import numpy as np
from fastapi.concurrency import run_in_threadpool

from .asr_service import ASRError, ASRService
from .metrics_service import StreamMetrics, system_snapshot
from .stream_session import StreamSession

log = logging.getLogger("asr.stream")
SR = 16_000
FRAME = 320                      # 20 ms, used to look for a quiet cut point
MIN_FINAL_TAIL_S = 0.3           # a shorter leftover is ignored (too short to transcribe reliably)


def join_text(a: str, b: str) -> str:
    """Join transcript pieces; no space when the boundary is Chinese/Japanese text."""
    if not a:
        return b
    if not b:
        return a
    cjk = lambda ch: ord(ch) >= 0x2E80
    return a + b if (cjk(a[-1]) or cjk(b[0])) else f"{a} {b}"


def quiet_split(audio: np.ndarray, start: int, end: int, window_s: float = 3.0,
                guard_s: float = 0.5) -> int:
    """Sample index of the quietest 20 ms frame in [end-window, end-guard], within the segment."""
    lo = max(start + SR, end - int(window_s * SR))      # keep at least 1 s in the committed part
    hi = end - int(guard_s * SR)
    if hi - lo < FRAME:
        return end
    n = (hi - lo) // FRAME
    frames = audio[lo:lo + n * FRAME].reshape(n, FRAME)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    return lo + int(rms.argmin()) * FRAME


class StreamTranscriber:
    def __init__(self, session: StreamSession, asr: ASRService, slots: asyncio.Semaphore,
                 send: Callable[[dict], Awaitable[None]],
                 update_interval_s: float, max_segment_s: float, min_audio_s: float):
        self.s, self.asr, self.slots, self.send = session, asr, slots, send
        self.update_samples = int(update_interval_s * SR)
        self.max_segment = int(max_segment_s * SR)
        self.min_samples = int(min_audio_s * SR)
        self.metrics = StreamMetrics()
        self.committed = ""            # permanent text of finished segments
        self.tail = ""                 # latest (still changing) text of the current segment
        self.seg_start = 0             # sample index where the current segment begins
        self.last_end = 0              # samples covered by the latest inference
        self.tail_valid = False        # self.tail covers audio up to last_end
        self.language = session.language
        self.ended = False
        self.end_time: float | None = None
        self.wake = asyncio.Event()

    # --- called by the receive loop --------------------------------------------------
    def notify(self) -> None:
        self.wake.set()

    def finish(self) -> None:
        self.ended = True
        self.end_time = time.perf_counter()
        self.wake.set()

    # --- the transcription loop -------------------------------------------------------
    async def run(self) -> None:
        while True:
            await self.wake.wait()
            self.wake.clear()
            if self.ended:
                break
            await self._update()
        await self._final()

    async def _infer(self, audio: np.ndarray) -> str:
        t0 = time.perf_counter()
        async with self.slots:                       # at most N model runs at once
            queue_s = time.perf_counter() - t0
            res = await run_in_threadpool(self.asr.transcribe, audio, self.s.language)
        self.metrics.record(res.infer_s, queue_s)
        self.language = res.language or self.language
        return res.text.strip()

    async def _update(self) -> None:
        total = self.s.samples_received
        seg_len = total - self.seg_start
        if total - self.last_end < self.update_samples or seg_len < self.min_samples:
            return
        audio = self.s.audio()
        t_start = time.perf_counter()
        if seg_len >= self.max_segment:
            # commit the segment up to a quiet point; the remainder starts the next segment
            split = quiet_split(audio, self.seg_start, total)
            text = await self._infer(audio[self.seg_start:split])
            self.committed = join_text(self.committed, text)
            self.seg_start, self.last_end, self.tail, self.tail_valid = split, split, "", False
            covered = split
        else:
            self.tail = await self._infer(audio[self.seg_start:total])
            self.last_end, self.tail_valid, covered = total, True, total
        await self._emit("partial", covered, t_start)

    async def _emit(self, kind: str, covered: int, t_start: float, **extra) -> None:
        text = join_text(self.committed, self.tail)
        elapsed = self.s.elapsed_since_first_chunk()
        if text:
            self.metrics.mark_text(elapsed, self.s.audio_seconds)
        await self.send({
            "type": kind, "text": text, "committed_text": self.committed, "language": self.language,
            "audio_seconds_received": round(self.s.audio_seconds, 2),
            "audio_seconds_transcribed": round(covered / SR, 2),
            "window_seconds": round((covered - self.seg_start) / SR, 2),
            "inference_seconds": round(self.metrics.total_infer_s / max(self.metrics.inferences, 1), 2),
            "elapsed_seconds": round(elapsed, 2),
            "processing_seconds": round(time.perf_counter() - t_start, 2),
            **extra,
        })

    async def _final(self) -> None:
        total = self.s.samples_received
        t_start = time.perf_counter()
        if not (self.tail_valid and self.last_end == total):      # leftover audio not covered yet
            remaining = total - self.seg_start
            self.tail = (await self._infer(self.s.audio()[self.seg_start:total])
                         if remaining >= MIN_FINAL_TAIL_S * SR else "")
        m = self.metrics
        audio_s = self.s.audio_seconds
        await self._emit(
            "final", total, t_start,
            stream_id=self.s.stream_id, chunk_ms=self.s.chunk_ms,
            audio_seconds=round(audio_s, 2), chunks=self.s.chunks_received,
            inferences=m.inferences,
            total_inference_seconds=round(m.total_infer_s, 2),
            queue_seconds=round(m.total_queue_s, 2),
            rtf=round(m.total_infer_s / audio_s, 2) if audio_s else None,
            first_transcript_latency_seconds=None if m.first_text_latency_s is None else round(m.first_text_latency_s, 2),
            audio_seconds_at_first_text=None if m.audio_s_at_first_text is None else round(m.audio_s_at_first_text, 2),
            final_latency_seconds=round(time.perf_counter() - (self.end_time or t_start), 2),
            **system_snapshot(),
        )
