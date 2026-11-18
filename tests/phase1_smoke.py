"""Phase 1 smoke test: load Qwen3-ASR-0.6B-hf on CPU and transcribe one WAV.

Run from the project root:  python tests/phase1_smoke.py [samples/english.wav]
"""
import os
import sys
import time

os.environ["CUDA_VISIBLE_DEVICES"] = ""  # keep the GPU out of the benchmark
os.environ.setdefault("HF_HOME", r"D:\hf_cache")  # keep the multi-GB model off C:

import psutil
import soundfile as sf
import torch
from transformers import AutoModelForMultimodalLM, AutoProcessor

MODEL_ID = "Qwen/Qwen3-ASR-0.6B-hf"
wav_path = sys.argv[1] if len(sys.argv) > 1 else "samples/english.wav"
dtype = torch.bfloat16 if "--bf16" in sys.argv else torch.float32

info = sf.info(wav_path)
print(f"audio: {wav_path} | {info.samplerate} Hz | {info.channels} ch | {info.duration:.2f}s | {info.subtype}")
assert info.samplerate == 16000 and info.channels == 1, "expected 16 kHz mono WAV"

proc = psutil.Process()
rss = lambda: proc.memory_info().rss / 1e9
print(f"torch {torch.__version__} | CUDA available: {torch.cuda.is_available()} | threads: {torch.get_num_threads()} | dtype: {dtype}")

t = time.perf_counter()
processor = AutoProcessor.from_pretrained(MODEL_ID)
model = AutoModelForMultimodalLM.from_pretrained(MODEL_ID, device_map="cpu", dtype=dtype)
model.eval()
load_s = time.perf_counter() - t
print(f"load: {load_s:.1f}s | RAM after load: {rss():.2f} GB | device: {model.device}")

for run in (1, 2):  # run 1 includes warm-up, run 2 is the steadier number
    proc.cpu_percent(None)
    t = time.perf_counter()
    inputs = processor.apply_transcription_request(audio=wav_path).to(model.device, model.dtype)
    with torch.inference_mode():
        output_ids = model.generate(**inputs, max_new_tokens=256)
    text = processor.decode(output_ids[:, inputs["input_ids"].shape[1]:], return_format="transcription_only")[0]
    dt = time.perf_counter() - t
    print(f"run {run}: {dt:.2f}s | RTF {dt / info.duration:.2f} | CPU(process) {proc.cpu_percent(None):.0f}% "
          f"| peak RSS {proc.memory_info().peak_wset / 1e9:.2f} GB")
    print(f"  transcript: {text}")
