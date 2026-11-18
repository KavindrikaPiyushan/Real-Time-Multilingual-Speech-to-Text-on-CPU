"""Loads Qwen3-ASR and transcribes audio on CPU. No knowledge of WebSockets or the UI."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

# Keep the GPU out of the benchmark. Must be set before torch initialises CUDA.
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("HF_HOME", r"D:\hf_cache")

import numpy as np
import torch
from transformers import AutoModelForMultimodalLM, AutoProcessor

from .audio_service import TARGET_SR

MODEL_ID = "Qwen/Qwen3-ASR-0.6B-hf"


class ASRError(RuntimeError):
    """Model loading or inference failed."""


@dataclass
class TranscriptionResult:
    text: str
    language: str | None      # None when the language was forced by the caller
    audio_s: float
    infer_s: float

    @property
    def rtf(self) -> float:
        """Real-time factor = processing time / audio duration (below 1 is faster than real time)."""
        return self.infer_s / self.audio_s if self.audio_s else float("inf")


class ASRService:
    def __init__(self, model_id: str = MODEL_ID, dtype: torch.dtype = torch.float32,
                 num_threads: int | None = None):
        self.model_id = model_id
        self.dtype = dtype
        if num_threads:
            torch.set_num_threads(num_threads)
        self.processor = None
        self.model = None
        self.load_s = 0.0

    def load(self) -> None:
        t = time.perf_counter()
        try:
            self.processor = AutoProcessor.from_pretrained(self.model_id)
            self.model = AutoModelForMultimodalLM.from_pretrained(
                self.model_id, device_map="cpu", dtype=self.dtype)
            self.model.eval()
        except Exception as exc:
            raise ASRError(f"Failed to load model {self.model_id}: {exc}") from exc
        self.load_s = time.perf_counter() - t

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def transcribe(self, audio: np.ndarray, language: str | None = None,
                   max_new_tokens: int = 256) -> TranscriptionResult:
        """Transcribe 16 kHz mono float32 samples. language: e.g. "English", "Chinese",
        "Indonesian", or None for automatic language detection."""
        if not self.loaded:
            raise ASRError("Model is not loaded. Call load() first.")
        audio_s = len(audio) / TARGET_SR
        t = time.perf_counter()
        try:
            inputs = self.processor.apply_transcription_request(
                audio=audio, language=language).to(self.model.device, self.model.dtype)
            with torch.inference_mode():
                out = self.model.generate(**inputs, max_new_tokens=max_new_tokens)
            decoded = self.processor.decode(
                out[:, inputs["input_ids"].shape[1]:], return_format="parsed")[0]
        except Exception as exc:
            raise ASRError(f"Transcription failed: {exc}") from exc
        infer_s = time.perf_counter() - t

        if isinstance(decoded, dict):
            return TranscriptionResult(decoded.get("transcription", ""), decoded.get("language"),
                                       audio_s, infer_s)
        return TranscriptionResult(str(decoded), None, audio_s, infer_s)
