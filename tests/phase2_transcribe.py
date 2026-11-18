"""Phase 2: standalone ASR on the three sample languages (CPU only).

Run from the project root:  python tests/phase2_transcribe.py
Writes reports/phase2_results.csv
"""
import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import psutil

from app.services.asr_service import ASRService
from app.services.audio_service import AudioError, load_wav

# (file, forced language name, reference file or None, error metric)
SAMPLES = [
    ("english.wav", "English", "english.txt", "WER"),
    ("mandarin_tts.wav", "Chinese", "mandarin_tts.txt", "CER"),
    ("indonesian_tts.wav", "Indonesian", "indonesian_tts.txt", "WER"),
]


def error_rate(ref: str, hyp: str, metric: str) -> float | None:
    import re
    import jiwer
    norm = lambda s: re.sub(r"[^\w\s]", "", s.lower()).strip()  # lowercase, strip punctuation
    ref, hyp = norm(ref), norm(hyp)
    if not ref:
        return None
    if metric == "CER":
        return jiwer.cer(ref.replace(" ", ""), hyp.replace(" ", ""))
    return jiwer.wer(ref, hyp)


def main() -> None:
    svc = ASRService()
    proc = psutil.Process()
    svc.load()
    print(f"model loaded in {svc.load_s:.1f}s | RAM {proc.memory_info().rss / 1e9:.2f} GB\n")

    rows = []
    for fname, lang, ref_name, metric in SAMPLES:
        path = ROOT / "samples" / fname
        try:
            audio, info = load_wav(path, strict=True)
        except (AudioError, FileNotFoundError) as exc:
            print(f"[skip] {fname}: {exc}")
            continue
        ref_path = ROOT / "samples" / "references" / ref_name
        ref = ref_path.read_text(encoding="utf-8") if ref_path.exists() else ""

        for mode, forced in (("auto-detect", None), ("forced", lang)):
            proc.cpu_percent(None)
            res = svc.transcribe(audio, language=forced)
            cpu = proc.cpu_percent(None)
            err = error_rate(ref, res.text, metric) if ref else None
            rows.append({
                "file": fname, "mode": mode, "detected_language": res.language or "",
                "audio_s": round(res.audio_s, 2), "infer_s": round(res.infer_s, 2),
                "rtf": round(res.rtf, 2), "cpu_pct": round(cpu), "rss_gb": round(proc.memory_info().rss / 1e9, 2),
                "metric": metric, "error_rate": "" if err is None else round(err, 3),
                "transcript": res.text,
            })
            print(f"{fname} [{mode}] lang={res.language} | {res.infer_s:.2f}s for {res.audio_s:.1f}s "
                  f"(RTF {res.rtf:.2f}) | {metric}={'n/a' if err is None else f'{err:.3f}'}\n  {res.text}\n")

    out = ROOT / "reports" / "phase2_results.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
