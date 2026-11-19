"""Phase 7: can quantization / lower precision speed up Qwen3-ASR on this CPU?

    python tests/qwen_quant_experiment.py     -> reports/qwen_quantization_results.csv
Variants (offline, whole file, same clips): float32 baseline, bfloat16, and PyTorch dynamic int8 quantization
of the Linear layers (torch.ao.quantization.quantize_dynamic). Reports time, RAM and error rate.
"""
import csv
import gc
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "tests"))

import psutil
import torch

from app.services.asr_service import ASRService
from app.services.audio_service import load_wav
from textmetrics import error_rate

CLIPS = [("english.wav", "English", "english.txt", "WER"), ("mandarin.wav", "Chinese", "mandarin.txt", "CER"),
         ("indonesian.wav", "Indonesian", "indonesian.txt", "WER")]


def build(variant: str) -> ASRService:
    svc = ASRService(dtype=torch.bfloat16 if variant == "bfloat16" else torch.float32)
    svc.load()
    if variant == "int8-dynamic":
        svc.model = torch.ao.quantization.quantize_dynamic(svc.model, {torch.nn.Linear}, dtype=torch.qint8)
    return svc


def main():
    proc = psutil.Process()
    rows = []
    for variant in ("float32", "bfloat16", "int8-dynamic"):
        gc.collect()
        try:
            svc = build(variant)
        except Exception as exc:
            print(variant, "FAILED to build:", repr(exc)[:200])
            rows.append({"variant": variant, "clip": "-", "error": repr(exc)[:200]})
            continue
        rss = proc.memory_info().rss / 1e6
        for fname, lang, ref_name, metric in CLIPS:
            audio, _ = load_wav(ROOT / "samples" / fname, strict=True)
            ref = (ROOT / "samples" / "references" / ref_name).read_text(encoding="utf-8")
            try:
                svc.transcribe(audio[:16000 * 3], lang)         # warm-up, not measured
                res = svc.transcribe(audio, lang)
            except Exception as exc:
                print(variant, fname, "FAILED:", repr(exc)[:200])
                rows.append({"variant": variant, "clip": fname, "error": repr(exc)[:200]})
                continue
            row = {"variant": variant, "clip": fname, "audio_s": round(res.audio_s, 1), "infer_s": round(res.infer_s, 2),
                   "rtf": round(res.rtf, 2), "rss_mb": round(max(rss, proc.memory_info().rss / 1e6)),
                   "metric": metric, "error_rate": round(error_rate(ref, res.text, metric), 3), "transcript": res.text}
            rows.append(row)
            print({k: v for k, v in row.items() if k != "transcript"}, flush=True)
        del svc
        gc.collect()
    fields = list(dict.fromkeys(k for r in rows for k in r))
    out = ROOT / "reports" / "qwen_quantization_results.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print("saved", out)


main()
