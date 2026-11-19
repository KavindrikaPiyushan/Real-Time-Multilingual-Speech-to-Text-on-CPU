"""Phase 7: whisper.cpp (C++ runtime) on the same clips, same machine, CPU only.

    python tests/whisper_cpp_benchmark.py     -> reports/whisper_cpp_results.csv
Offline (whole file) transcription with whisper-cli; the language is forced like the Qwen runs.
Time = wall clock for the whole process (includes model loading); 'infer_s' = whisper's own total minus load time.
"""
import csv
import re
import subprocess
import time
from pathlib import Path

import psutil

from textmetrics import error_rate

ROOT = Path(__file__).resolve().parents[1]
CLI = Path(r"D:\asr_tools\whisper-v1.9.2\Release\whisper-cli.exe")
MODELS = Path(r"D:\asr_tools\models")
MODEL_FILES = ["ggml-base-q5_1.bin", "ggml-small-q5_1.bin", "ggml-small.bin", "ggml-large-v3-turbo-q5_0.bin"]
CLIPS = [("english.wav", "en", "english.txt", "WER", 11.10), ("mandarin.wav", "zh", "mandarin.txt", "CER", 15.74),
         ("indonesian.wav", "id", "indonesian.txt", "WER", 52.15)]
THREADS = 6
REPS = 2


def run(model: str, clip: str, lang: str):
    cmd = [str(CLI), "-m", str(MODELS / model), "-f", str(ROOT / "samples" / clip), "-l", lang,
           "-t", str(THREADS), "-nt", "-np"]
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
    err = err.decode("utf-8", "replace")
    num = lambda key: (float(m.group(1)) / 1000 if (m := re.search(rf"{key}\s*=\s*([\d.]+) ms", err)) else None)
    return {"text": " ".join(out.decode("utf-8", "replace").split()), "wall_s": wall,
            "load_s": num("load time"), "total_s": num("total time"),
            "rss_mb": peak / 1e6, "cpu_avg": sum(cpu) / len(cpu) if cpu else None, "rc": p.returncode}


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
                infer = (r["total_s"] - r["load_s"]) if r["total_s"] and r["load_s"] is not None else None
                row = {"model": model, "model_mb": round((MODELS / model).stat().st_size / 1e6), "clip": clip,
                       "rep": rep, "audio_s": audio_s, "wall_s": round(r["wall_s"], 1),
                       "load_s": None if r["load_s"] is None else round(r["load_s"], 1),
                       "infer_s": None if infer is None else round(infer, 1),
                       "rtf_infer": None if infer is None else round(infer / audio_s, 2),
                       "rss_mb": round(r["rss_mb"]), "cpu_avg_pct": round(r["cpu_avg"] or 0),
                       "metric": metric, "error_rate": round(error_rate(ref, r["text"], metric), 3),
                       "returncode": r["rc"], "transcript": r["text"]}
                rows.append(row)
                print({k: v for k, v in row.items() if k != "transcript"}, flush=True)
    out = ROOT / "reports" / "whisper_cpp_results.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("saved", out)


main()
