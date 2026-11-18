"""Phase 6: concurrency / load test. N simultaneous real-time streams = N call legs.

    python tests/load_test.py          -> reports/benchmark_results.csv
For each backend configuration the script starts its own server, measures model-load and idle resource use,
then runs 1, 2, 3, 4, 6 concurrent streams (English and Mandarin clips, alternating, staggered starts).

A level is "OK" when every stream finished without error AND the worst final latency <= FINAL_MAX_S
AND the average lag (audio received but not yet in the transcript) <= LAG_MAX_S. These thresholds are my
assumption of "acceptable for live use"; the raw numbers are saved so other thresholds can be applied.
"""
import asyncio
import csv
import statistics as st
import time
from pathlib import Path

from server_harness import Server
from stream_client import stream_file
from textmetrics import error_rate

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = [
    ("default (1 slot, update 2s, segment 10s)", {}),
    ("1 slot, update 4s, segment 10s", {"ASR_UPDATE_INTERVAL_S": 4}),
    ("2 slots x 3 threads, update 2s", {"ASR_MAX_CONCURRENT_INFERENCES": 2, "ASR_TORCH_THREADS": 3}),
]
LEVELS = [1, 2, 3, 4, 6]
CLIPS = [("english.wav", "English", "english.txt", "WER"), ("mandarin.wav", "Chinese", "mandarin.txt", "CER")]
OFFSETS = [0, 0.7, 1.4, 0.3, 1.1, 1.8]       # stagger so calls do not start in lockstep
FINAL_MAX_S, LAG_MAX_S = 10.0, 5.0


async def one_stream(i, url):
    fname, lang, ref_name, metric = CLIPS[i % len(CLIPS)]
    await asyncio.sleep(OFFSETS[i % len(OFFSETS)])
    try:
        r = await stream_file(str(ROOT / "samples" / fname), lang, 2000, url=url)
    except Exception as exc:               # a dropped connection counts as a failed stream
        return {"error": f"{type(exc).__name__}: {exc}"}
    if r["error"]:
        return {"error": str(r["error"])}
    lags = [p["audio_seconds_received"] - p["audio_seconds_transcribed"] for p in r["partials"]]
    ref = (ROOT / "samples" / "references" / ref_name).read_text(encoding="utf-8")
    return {"error": None, "first_text": r.get("first_text_client_s"), "final_latency": r["final_client_latency_s"],
            "mean_lag": st.mean(lags) if lags else 0, "max_lag": max(lags) if lags else 0,
            "model_s": r["final"]["total_inference_seconds"], "audio_s": r["final"]["audio_seconds"],
            "queue_s": r["final"]["queue_seconds"], "err": error_rate(ref, r["final"]["text"], metric)}


async def run_level(srv, n):
    t0 = time.perf_counter()
    res = await asyncio.gather(*(one_stream(i, srv.url) for i in range(n)))
    t1 = time.perf_counter()
    ok = [r for r in res if not r["error"]]
    row = {"streams": n, "completed": len(ok), "failed": n - len(ok), "wall_s": round(t1 - t0, 1)}
    if ok:
        row.update({
            "first_text_avg_s": round(st.mean(r["first_text"] for r in ok), 1),
            "final_latency_max_s": round(max(r["final_latency"] for r in ok), 1),
            "mean_lag_s": round(st.mean(r["mean_lag"] for r in ok), 1),
            "max_lag_s": round(max(r["max_lag"] for r in ok), 1),
            "model_s_total": round(sum(r["model_s"] for r in ok), 1),
            "queue_s_total": round(sum(r["queue_s"] for r in ok), 1),
            "audio_s_total": round(sum(r["audio_s"] for r in ok), 1),
            "error_rate_avg": round(st.mean(r["err"] for r in ok), 3),
        })
    row.update(srv.sampler.summary(t0, t1))
    row["ok"] = bool(ok) and row["failed"] == 0 and row["final_latency_max_s"] <= FINAL_MAX_S and row["mean_lag_s"] <= LAG_MAX_S
    errs = [r["error"] for r in res if r["error"]]
    row["errors"] = "; ".join(errs)[:200]
    return row


async def main():
    rows = []
    for cfg_name, env in CONFIGS:
        with Server(port=8002, **env) as srv:
            idle = srv.idle_summary(5)
            load = srv.load_summary()
            base = {"config": cfg_name}
            rows.append({**base, "streams": "load", **{k: load[k] for k in ("proc_cpu_avg", "proc_cpu_peak", "rss_peak_mb")}})
            rows.append({**base, "streams": "idle", **{k: idle[k] for k in ("proc_cpu_avg", "proc_cpu_peak", "rss_peak_mb")}})
            print(f"[{cfg_name}] model load: CPU avg {load['proc_cpu_avg']}% RAM peak {load['rss_peak_mb']} MB | "
                  f"idle: CPU {idle['proc_cpu_avg']}% RAM {idle['rss_peak_mb']} MB", flush=True)
            for n in LEVELS:
                row = {**base, **await run_level(srv, n)}
                rows.append(row)
                print({k: v for k, v in row.items() if k not in ("config", "errors")}, row["errors"], flush=True)
                await asyncio.sleep(3)
                if row["failed"] == n:      # nothing worked at this level: no point going higher
                    break
    fields = list(dict.fromkeys(k for r in rows for k in r))
    out = ROOT / "reports" / "benchmark_results.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print("saved", out)


asyncio.run(main())
