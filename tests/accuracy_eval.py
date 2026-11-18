"""Phase 6: accuracy (WER for English/Indonesian, CER for Mandarin), offline vs streaming.

    python tests/accuracy_eval.py          -> reports/accuracy_results.csv
Offline = whole file through POST /api/transcribe. Streaming = real-time paced WebSocket stream (final text).
Normalisation: lowercase, punctuation removed; CER ignores spaces.
"""
import asyncio
import csv
import statistics as st
from pathlib import Path

import httpx

from server_harness import Server
from stream_client import stream_file
from textmetrics import error_rate

ROOT = Path(__file__).resolve().parents[1]
CLIPS = [  # file, language, reference, metric
    ("english.wav", "English", "english.txt", "WER"),
    ("mandarin.wav", "Chinese", "mandarin.txt", "CER"),
    ("indonesian.wav", "Indonesian", "indonesian.txt", "WER"),
]
STREAM_REPS = 2


def ref_text(name):
    return (ROOT / "samples" / "references" / name).read_text(encoding="utf-8")


async def main():
    rows = []
    with Server(port=8002) as srv:
        for fname, lang, ref_name, metric in CLIPS:
            path = ROOT / "samples" / fname
            ref = ref_text(ref_name)
            with httpx.Client(timeout=300) as c:
                r = c.post(f"{srv.http}/api/transcribe", data={"language": lang},
                           files={"file": (fname, path.read_bytes(), "audio/wav")}).json()
            rows.append({"clip": fname, "language": lang, "mode": "offline", "metric": metric, "run": 1,
                         "error_rate": round(error_rate(ref, r["text"], metric), 3), "transcript": r["text"]})
            print(rows[-1]["clip"], "offline", rows[-1]["error_rate"], flush=True)
            for rep in range(1, STREAM_REPS + 1):
                s = await stream_file(str(path), lang, 2000, url=srv.url)
                text = s["final"]["text"]
                rows.append({"clip": fname, "language": lang, "mode": "streaming", "metric": metric, "run": rep,
                             "error_rate": round(error_rate(ref, text, metric), 3), "transcript": text})
                print(rows[-1]["clip"], "streaming", rows[-1]["error_rate"], flush=True)
    out = ROOT / "reports" / "accuracy_results.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("\nclip            mode       metric  error_rate (mean of runs)")
    for fname, *_ , metric in CLIPS:
        for mode in ("offline", "streaming"):
            v = [r["error_rate"] for r in rows if r["clip"] == fname and r["mode"] == mode]
            print(f"{fname:15} {mode:10} {metric:6}  {st.mean(v):.3f}  {v}")
    print("saved", out)


asyncio.run(main())
