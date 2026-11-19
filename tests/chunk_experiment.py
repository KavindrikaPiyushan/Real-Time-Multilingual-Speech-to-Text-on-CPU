"""Phase 5: effect of the audio CHUNK size (how audio is sent) on latency and accuracy.

Needs the backend running with default settings.  python tests/chunk_experiment.py [ws-url]
Writes reports/chunk_size_results.csv
"""
import asyncio
import csv
import sys
from pathlib import Path

from stream_client import URL, stream_file
from textmetrics import error_rate

ROOT = Path(__file__).resolve().parents[1]
url = sys.argv[1] if len(sys.argv) > 1 else URL
CLIPS = [("english.wav", "English", "english.txt", "WER"), ("mandarin.wav", "Chinese", "mandarin.txt", "CER")]
CHUNKS_MS = [500, 1000, 2000, 5000]
REPS = 2


async def main():
    rows = []
    for rep in range(1, REPS + 1):
        for chunk_ms in CHUNKS_MS:
            for fname, lang, ref_name, metric in CLIPS:
                r = await stream_file(str(ROOT / "samples" / fname), lang, chunk_ms, url=url)
                if r["error"]:
                    print("ERROR", fname, chunk_ms, r["error"])
                    continue
                f = r["final"]
                ref = (ROOT / "samples" / "references" / ref_name).read_text(encoding="utf-8")
                row = {
                    "clip": fname, "chunk_ms": chunk_ms, "rep": rep, "audio_s": f["audio_seconds"],
                    "chunks": f["chunks"], "first_text_s": r.get("first_text_client_s"),
                    "final_latency_s": r["final_client_latency_s"], "inferences": f["inferences"],
                    "model_s": f["total_inference_seconds"], "rtf": f["rtf"],
                    "metric": metric, "error_rate": round(error_rate(ref, f["text"], metric), 3),
                    "transcript": f["text"],
                }
                rows.append(row)
                print({k: v for k, v in row.items() if k != "transcript"}, flush=True)
    out = ROOT / "reports" / "chunk_size_results.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("saved", out)


asyncio.run(main())
