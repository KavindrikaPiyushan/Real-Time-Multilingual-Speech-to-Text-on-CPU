"""Unit tests for the streaming logic using a FAKE model (fast, deterministic, no GPU/CPU load).
Run: backend/.venv/Scripts/python.exe -m pytest tests/test_stream_transcriber.py -q
"""
import asyncio
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.api.websocket import run_transcriber  # noqa: E402
from app.services.asr_service import ASRError, TranscriptionResult  # noqa: E402
from app.services.stream_session import ProtocolError, StreamSession  # noqa: E402
from app.services.stream_transcriber import SR, StreamTranscriber, join_text, quiet_split  # noqa: E402


class FakeASR:
    """Returns the number of samples it was given as its 'transcript', so nothing can be lost silently."""
    loaded = True

    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def transcribe(self, audio, language=None, **_):
        if self.fail:
            raise ASRError("boom")
        self.calls.append(len(audio))
        return TranscriptionResult(str(len(audio)), language or "English", len(audio) / SR, 0.01)


def pcm(seconds, loud=True):
    rng = np.random.default_rng(0)
    x = (rng.normal(0, 3000 if loud else 0, int(seconds * SR))).astype("<i2")
    return x.tobytes()


def make(asr, sent, max_segment_s=10.0, update_s=2.0):
    session = StreamSession(language="English", max_seconds=600)
    t = StreamTranscriber(session, asr, asyncio.Semaphore(1), lambda m: _collect(sent, m),
                          update_s, max_segment_s, 1.0)
    return session, t


async def _collect(sent, msg):
    sent.append(msg)


def test_join_text():
    assert join_text("hello", "world") == "hello world"
    assert join_text("你好", "世界") == "你好世界"
    assert join_text("hello", "你好") == "hello你好"
    assert join_text("", "x") == "x" and join_text("x", "") == "x"


def test_quiet_split_picks_the_silent_gap():
    audio = np.random.default_rng(1).normal(0, 0.3, int(10.5 * SR)).astype(np.float32)
    audio[int(8.0 * SR):int(8.2 * SR)] = 0           # a pause at 8.0-8.2 s
    split = quiet_split(audio, 0, len(audio))
    assert 8.0 * SR <= split <= 8.2 * SR


def test_segments_are_bounded_and_no_audio_is_lost_or_duplicated():
    async def go():
        asr, sent = FakeASR(), []
        session, t = make(asr, sent)
        for _ in range(13):                           # 26 s of audio in 2 s chunks
            session.add_pcm(pcm(2))
            await t._update()
        t.finish()
        await t._final()
        return asr, sent, session
    asr, sent, session = asyncio.run(go())
    final = sent[-1]
    assert final["type"] == "final"
    # every inference saw a bounded window (max segment + one chunk of slack), never the whole stream
    assert max(asr.calls) <= 12 * SR
    # text is the sample count of each committed segment + the tail: they add up to ALL audio exactly once
    assert sum(int(x) for x in final["text"].split()) == session.samples_received
    assert len(final["committed_text"].split()) >= 2   # several segments were committed


def test_final_reuses_last_partial_when_nothing_new_arrived():
    async def go():
        asr, sent = FakeASR(), []
        session, t = make(asr, sent)
        session.add_pcm(pcm(3))
        await t._update()                              # one partial covering all 3 s
        t.finish()
        await t._final()
        return asr, sent
    asr, sent = asyncio.run(go())
    assert len(asr.calls) == 1                         # final did not run the model again
    assert sent[-1]["type"] == "final" and sent[-1]["text"] == str(3 * SR)


def test_too_little_audio_is_not_transcribed():
    async def go():
        asr, sent = FakeASR(), []
        session, t = make(asr, sent)
        session.add_pcm(pcm(0.2))
        await t._update()
        t.finish()
        await t._final()
        return asr, sent
    asr, sent = asyncio.run(go())
    assert asr.calls == [] and sent[-1]["text"] == ""


def test_model_failure_is_reported_to_the_client():
    errors = []

    class Out:
        async def error(self, code, message, close_code=1008):
            errors.append((code, close_code))

    async def go():
        session, t = make(FakeASR(fail=True), [])
        session.add_pcm(pcm(3))
        task = asyncio.create_task(run_transcriber(t, Out(), "x"))
        t.notify()
        await asyncio.sleep(0.2)
        t.finish()
        await task
    asyncio.run(go())
    assert errors == [("asr_failed", 1011)]


def test_stream_limit_enforced():
    session = StreamSession(language=None, max_seconds=2)
    session.add_pcm(pcm(1.5))
    with pytest.raises(ProtocolError) as e:
        session.add_pcm(pcm(1.5))
    assert e.value.code == "stream_too_long"
