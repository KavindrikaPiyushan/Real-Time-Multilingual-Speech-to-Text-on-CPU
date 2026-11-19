# Phase 6 findings: performance, accuracy and concurrency (measured)

Machine: Intel Core i5-10500H (6 cores / 12 threads), 24 GB RAM, Windows 11, **CPU only** (GTX 1650 Ti not used).
Model/runtime: Qwen3-ASR-0.6B-hf, Hugging Face Transformers, float32, PyTorch 2.15 (CPU), 6 torch threads.
Backend: FastAPI, one model instance in one process, application-level streaming (2 s chunks, 2 s update interval, 10 s segments unless stated).
All streams are paced at real-time speed. Scripts: `tests/accuracy_eval.py`, `tests/load_test.py` (harness: `tests/server_harness.py`).
Raw data: `accuracy_results.csv`, `benchmark_results.csv`.

## 1. Latency (single stream, English 11.1 s clip, default settings; from the load test, N=1)
| Metric | Value |
|---|---|
| First transcript appears | about 2.9 s after the stream starts (about 1 s of compute after the first 2 s of audio exists) |
| Final transcript after the last audio is sent | about 6.5 s (compute for the unfinished tail plus any update still running) |
| Model compute for the whole clip | 14.3 s, i.e. RTF about 1.3 (the clip is transcribed several times, each window again) |
| Partial lag (audio received but not yet in transcript) | mean 1.3 s, max 3.1 s |
Offline single pass over the same clip (Phase 2): about 5-6 s, RTF about 0.5.
With a 4 s update interval: first text about 5.9 s, final about 5.1 s, compute 10.1 s (RTF 0.9).

## 2. Accuracy (reference text written by the speaker; lowercase, punctuation removed, CER ignores spaces)
| Clip | Metric | Offline (whole file) | Streaming (2 runs) |
|---|---|---|---|
| English, 11 s, own voice | WER | 0.353 | 0.353, 0.353 |
| Mandarin, 16 s, own voice | CER | 0.000 | 0.000, 0.000 |
| Indonesian, 52 s, casual conversation | WER | 0.442 | 0.363, 0.469 |
- English errors are almost entirely the product name "Qwen3-ASR" (heard as "Q and three") plus "They released" -> "The release".
- Indonesian errors mix real misrecognitions with spelling variants that WER counts as errors ("enggak" vs "nggak").
- Streaming accuracy equals offline for English and Mandarin; Indonesian varies by about 0.1 between runs (segment cut points depend on timing).
- Only three short clips from one speaker: these numbers show the pipeline works, they are not a general accuracy benchmark.
- During the load test, per-stream accuracy did not change under load (average error rate matched the single-stream values).

## 3. CPU and memory (backend process tree, sampled every 0.5 s)
| Situation | CPU (100% = one core) | RAM |
|---|---|---|
| Model loading (about 6 s when cached) | average about 200%, peak about 1000% | rises to about 3.6 GB |
| Idle, model loaded | about 0% | about 3.6 GB |
| 1 stream running | average 215-430%, peak about 610% (about 6 cores busy) | about 3.8 GB peak |
| 6 streams | average about 540%, peak about 612% | about 3.9-4.0 GB peak |
- CPU saturates at about 6 busy cores (the torch thread count) with a single stream; more streams only queue behind it.
- Memory is dominated by the one shared model (about 3.6 GB). The first stream added about 200 MB (working memory for inference); each further stream added only about 15 MB (3.81 GB at 1 stream, 3.89 GB at 6).
- Measurements refer to the backend process tree only, not the whole machine (system-wide CPU was about 45-55% under load).

## 4. Concurrency (N simultaneous real-time streams, English and Mandarin clips alternating, starts staggered by 0-1.8 s)
A level is **OK** if no stream failed, the worst final latency is at most 10 s and the average lag is at most 5 s (my assumption of acceptable live use).

**Default configuration (1 inference at a time, update 2 s):**
| Streams | First text (avg) | Worst final latency | Lag avg / max | Queue wait (total) | Process CPU avg | RAM peak | OK? |
|---|---|---|---|---|---|---|---|
| 1 | 2.9 s | 6.5 s | 1.3 / 3.1 s | 0 s | 428% | 3.8 GB | yes |
| 2 | 3.1 s | 11.7 s | 2.2 / 6.9 s | 18 s | 499% | 3.8 GB | no |
| 3 | 3.2 s | 18.6 s | 2.6 / 6.0 s | 45 s | 523% | 3.8 GB | no |
| 4 | 3.8 s | 20.2 s | 3.9 / 7.7 s | 80 s | 527% | 3.9 GB | no |
| 6 | 4.5 s | 35.7 s | 4.6 / 9.7 s | 192 s | 547% | 3.9 GB | no |

**Other configurations (same clips):**
| Configuration | Largest OK level | Notes |
|---|---|---|
| 1 inference at a time, update 4 s | **2 streams** (worst final 7.8 s) | first text about 6 s; 3 streams: worst final 19.7 s |
| 2 inferences at a time x 3 threads each, update 2 s | **2 streams** (worst final 7.7 s, no queueing) | per-inference time is slower under contention (total model time 34 s vs 23 s for 2 streams), 3 streams: worst final 14.9 s |

Observations
- **Every level completed with no failed streams or errors.** The system degrades by getting slower (queueing), not by breaking.
- **The bottleneck is CPU compute for model inference.** One inference already uses about 6 cores, so concurrent streams wait in the queue.
  Queue wait grows from 0 s (1 stream) to about 190 s total (6 streams) while memory barely grows.
- Running two inferences at once cut latency for 2 streams but used more total compute, and gave no gain at 3+ streams: the CPU is already full.
- First-text latency stays about 3 s (it only needs the first small window) while the final latency grows with load.
- **Measured capacity of this laptop: 2 concurrent streams within my latency criteria** (with a 4 s update interval, or 2 slots x 3 threads), **1 with the default settings**.
  With sustained dense speech (the 52 s Indonesian clip needs RTF about 0.9-1.1 for one stream) even 1 stream is at the limit.

## 5. Provisional sizing (an estimate, to be finished in Phase 8)
Assumptions: capacity of one 6-core / 12-thread machine = 2 streams of this workload (measured best case); linear scaling; 30% headroom; one model process per machine
(about 4 GB RAM; RAM is not the limit). For 50 / 100 / 200 / 500 / 1000 calls this gives about 33 / 65 / 130 / 325 / 650 such machines (each 12 vCPU, 8 GB).
That is an expensive upper-bound baseline for an unoptimised float32 re-transcription design; Phase 7 looks at what could reduce it (quantisation, native streaming, a faster runtime).

## 6. Limits of these measurements
- One laptop, one run per cell, short clips (11-16 s) from one speaker; laptop thermal throttling and background load were not controlled.
- The load clips were only English and Mandarin (alternating), not the denser Indonesian clip, which is more expensive per second.
- Calls started within 2 s of each other; real traffic would be more spread out, or more bursty.
- OK thresholds (10 s final latency, 5 s average lag) are my own assumption; the raw numbers are in the CSV.
- Capacity numbers apply to this application-level streaming design on this hardware, not to Qwen3-ASR in general.
