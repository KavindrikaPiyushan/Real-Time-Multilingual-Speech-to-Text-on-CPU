# Capacity estimates and server sizing

**Measured** = run on the test laptop. **Estimated** = calculated from the measurements with the assumptions below. Nothing in the 50-1000 rows was run.

## Test machine and what was measured
Intel Core i5-10500H (6 cores / 12 threads = 12 vCPU), 24 GB RAM, Windows 11, CPU only. Qwen3-ASR-0.6B (Transformers, float32), one model process, 6 torch threads,
application-level streaming (2 s chunks). Streams played at real-time speed, English and Mandarin clips (11-16 s) alternating. Full data: `phase6_findings.md`, `benchmark_results.csv`.

| Call legs | vCPU | RAM | Servers | Status | Result |
|---:|---|---|---|---|---|
| 1 | 12 (about 6 busy cores) | 3.8 GB | 1 laptop | **Measured** | Within criteria (worst final latency 6.5 s, avg lag 1.3 s) |
| 2 | 12 | 3.8 GB | 1 laptop | **Measured** | Within criteria only with a 4 s update interval or 2 inferences at once x 3 threads (worst final 7.7-7.8 s); default settings: 11.7 s (over the 10 s limit) |
| 3 / 4 / 6 | 12 | 3.8-3.9 GB | 1 laptop | **Measured** | Over the criteria: worst final latency 15-20 s / 20-29 s / 33-44 s. All streams still completed, only slower |

Acceptable = no stream failed, worst final latency <= 10 s, average lag <= 5 s (my own assumption; raw numbers are in the CSV).

## Estimates for larger loads
**Method.** One "worker" = one model process on 12 vCPU (the unit that was tested). Workers needed = calls / calls-per-worker x 1.3 headroom, rounded up.
A node = 48 vCPU / 32 GB RAM running 4 workers. RAM = 4 GB per worker (measured 3.6-3.9 GB).

### Scenario A: current design, as measured
Assumption: 1 worker serves **2 calls** (best measured result).
| Call legs | Workers | vCPU | RAM | Servers (48 vCPU / 32 GB) | Status |
|---:|---:|---:|---:|---:|---|
| 50 | 33 | 396 | 132 GB | 9 | Estimated |
| 100 | 65 | 780 | 260 GB | 17 | Estimated |
| 200 | 130 | 1,560 | 520 GB | 33 | Estimated |
| 500 | 325 | 3,900 | 1,300 GB | 82 | Estimated |
| 1,000 | 650 | 7,800 | 2,600 GB | 163 | Estimated |

### Scenario B: after optimisation (hypothetical)
Assumption: 1 worker serves **5 calls**. This is 2.5x the measured capacity and is a guess, based on one measurement: the streaming design spends about 2.5-3x the compute of a single offline pass
(English: 14 s of model time vs 5 s offline). Removing that repetition (native streaming, or a C++ runtime that supports it) and skipping silence could plausibly give that gain,
but none of it has been built or measured. Treat this scenario as a target to test, not a prediction.
| Call legs | Workers | vCPU | RAM | Servers (48 vCPU / 32 GB) | Status |
|---:|---:|---:|---:|---:|---|
| 50 | 13 | 156 | 52 GB | 4 | Estimated |
| 100 | 26 | 312 | 104 GB | 7 | Estimated |
| 200 | 52 | 624 | 208 GB | 13 | Estimated |
| 500 | 130 | 1,560 | 520 GB | 33 | Estimated |
| 1,000 | 260 | 3,120 | 1,040 GB | 65 | Estimated |

## Assumptions and why the real number may differ
- **Linear scaling.** Measured only up to 6 streams on one machine. Real systems lose some efficiency to memory-bandwidth contention (4 workers on one node), network and load-balancer overhead, and uneven load. This probably means more servers than shown.
- **Speech density.** Capacity depends on how much people talk: the dense 52 s Indonesian clip cost about 0.9 s of compute per second of audio for one stream alone (so one stream already fills a worker),
  while the English and Mandarin clips are lighter. The sizing used the lighter clips, so Scenario A may be optimistic for chatty calls and pessimistic for calls with long silences.
- **Cloud vCPU = a hyperthread.** I counted 12 vCPU per tested 6-core machine. Different CPUs (newer cores, AVX-512, many more cores per node) will change the per-worker capacity, which must be re-measured on the target hardware.
- **Concurrency is all at once.** The sizing assumes every call is active speech at the same time. Real call legs are idle part of the time and calls start and end at different moments, so average load is lower than peak.
- **Headroom 30%** covers bursts, failover and the slower first call after a deploy. It is a rule of thumb.
- **Memory.** Each worker holds its own copy of the model (about 3.6 GB); per-stream memory is small (about 15 MB measured), so CPU, not RAM, decides the server count. Sharing one model across more threads in a bigger process was not tested.
- **GPU.** Not considered (outside the assignment); a GPU service would change the numbers entirely.
- **Latency target.** The estimates keep the measured criteria (final latency <= 10 s). A looser or stricter target changes calls-per-worker directly.
