"""Phase 8: Qwen3-ASR-0.6B GGUF in a C++ runtime (transcribe.cpp), same clips, same machine, CPU only.

    python tests/transcribe_cpp_benchmark.py     -> reports/transcribe_cpp_results.csv
Offline (whole file) transcription with transcribe-cli --backend cpu; language forced like the other runs.
Time = wall clock for the whole process (includes model loading). RSS/CPU sampled like whisper_cpp_benchmark.py.
"""
import csv
import subprocess
import tempfile
import time
from pathlib import Path

import psutil

from textmetrics import error_rate

ROOT = Path(__file__).resolve().parents[1]
CLI = Path(r"D:\asr_tools\transcribe.cpp-src\build\bin\Release\transcribe-cli.exe")
MODELS = Path(r"D:\asr_tools\models\qwen3gguf")
MODEL_FILES = ["Qwen3-ASR-0.6B-Q5_K_M.gguf", "Qwen3-ASR-0.6B-Q8_0.gguf"]  # F16 skipped: ~1.9 GB at ~0.5 MB/s
CLIPS = [("english.wav", "en", "english.txt", "WER", 11.10), ("mandarin.wav", "zh", "mandarin.txt", "CER", 15.74),
         ("indonesian.wav", "id", "indonesian.txt", "WER", 52.15)]
THREADS = 6
REPS = 2


def run(model: str, clip: str, lang: str):
    txt = Path(tempfile.gettempdir()) / "transcribe_cpp_out.txt"
    txt.unlink(missing_ok=True)
    cmd = [str(CLI), "-m", str(MODELS / model), "-l", lang, "--threads", str(THREADS), "--backend", "cpu", "-q",
           "-o", str(txt), str(ROOT / "samples" / clip)]  # stdout also carries metadata, so read the -o file
    t0 = time.perf_counter()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    ps = psutil.Process(p.pid)
    ps.cpu_percent(None)
    peak, cpu = 0, []
    while p.poll() is None:
        time.sleep(0.2)
        try:
            peak = max(peak, ps.memory_info().rss)
            cpu.append(ps.cpu_percent(None))
        except psutil.Error:
            break
    out, err = p.communicate()
    wall = time.perf_counter() - t0
    text = txt.read_text(encoding="utf-8") if txt.exists() else ""
    return {"text": " ".join(text.split()), "wall_s": wall, "rss_mb": peak / 1e6,
            "cpu_avg": sum(cpu) / len(cpu) if cpu else None, "rc": p.returncode,
            "err": err.decode("utf-8", "replace")[-300:]}


def main():
    rows = []
    for model in MODEL_FILES:
        if not (MODELS / model).exists():
            print("missing", model)
            continue
        for clip, lang, ref_name, metric, audio_s in CLIPS:
            ref = (ROOT / "samples" / "references" / ref_name).read_text(encoding="utf-8")
            for rep in range(1, REPS + 1):
                r = run(model, clip, lang)
                row = {"model": model, "model_mb": round((MODELS / model).stat().st_size / 1e6), "clip": clip,
                       "rep": rep, "audio_s": audio_s, "wall_s": round(r["wall_s"], 1),
                       "rtf_wall": round(r["wall_s"] / audio_s, 2), "rss_mb": round(r["rss_mb"]),
                       "cpu_avg_pct": round(r["cpu_avg"] or 0), "metric": metric,
                       "error_rate": round(error_rate(ref, r["text"], metric), 3),
                       "returncode": r["rc"], "transcript": r["text"]}
                rows.append(row)
                print({k: v for k, v in row.items() if k != "transcript"}, flush=True)
                if r["rc"]:
                    print("  stderr:", r["err"])
    out = ROOT / "reports" / "transcribe_cpp_results.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("saved", out)


main()
