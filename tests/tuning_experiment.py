"""Phase 5: effect of the PROCESSING settings (update interval, segment length) on lag, latency and accuracy.

Starts its own backend for each configuration on port 8002 (stop other heavy jobs first).
    python tests/tuning_experiment.py
Writes reports/tuning_results.csv
"""
import asyncio
import csv
import os
import subprocess
import time
import urllib.request
from pathlib import Path

from stream_client import stream_file
from textmetrics import error_rate

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
PORT = 8002
CONFIGS = [(2, 10), (4, 10), (3, 6), (4, 6)]      # (update interval s, max segment s); first = current default
CLIPS = [("english.wav", "English", "english.txt", "WER"),
         ("indonesian.wav", "Indonesian", "indonesian.txt", "WER")]


def start_server(update_s, segment_s):
    env = {**os.environ, "PYTHONUTF8": "1", "TQDM_DISABLE": "1",
           "ASR_UPDATE_INTERVAL_S": str(update_s), "ASR_MAX_SEGMENT_S": str(segment_s)}
    proc = subprocess.Popen([str(PY), "-m", "uvicorn", "app.main:app", "--port", str(PORT)],
                            cwd=ROOT / "backend", env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(90):
        time.sleep(1)
        try:
            if b'"model_loaded":true' in urllib.request.urlopen(f"http://localhost:{PORT}/api/health").read():
                return proc
        except Exception:
            pass
    proc.kill()
    raise RuntimeError("server did not start")


def stop_server(proc):
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    time.sleep(2)


async def main():
    rows = []
    for update_s, segment_s in CONFIGS:
        proc = start_server(update_s, segment_s)
        try:
            for fname, lang, ref_name, metric in CLIPS:
                r = await stream_file(str(ROOT / "samples" / fname), lang, 2000,
                                      url=f"ws://localhost:{PORT}/ws/stream")
                if r["error"]:
                    print("ERROR", update_s, segment_s, fname, r["error"])
                    continue
                f = r["final"]
                lags = [p["audio_seconds_received"] - p["audio_seconds_transcribed"] for p in r["partials"]]
                ref = (ROOT / "samples" / "references" / ref_name).read_text(encoding="utf-8")
                row = {
                    "update_s": update_s, "segment_s": segment_s, "clip": fname, "audio_s": f["audio_seconds"],
                    "first_text_s": r.get("first_text_client_s"), "final_latency_s": r["final_client_latency_s"],
                    "mean_lag_s": round(sum(lags) / len(lags), 1) if lags else None,
                    "max_lag_s": round(max(lags), 1) if lags else None,
                    "inferences": f["inferences"], "model_s": f["total_inference_seconds"], "rtf": f["rtf"],
                    "metric": metric, "error_rate": round(error_rate(ref, f["text"], metric), 3),
                }
                rows.append(row)
                print(row, flush=True)
        finally:
            stop_server(proc)
    out = ROOT / "reports" / "tuning_results.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("saved", out)


asyncio.run(main())
