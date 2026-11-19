# Technical report: real-time multilingual speech-to-text on CPU

Task: a web application that streams a WAV file in chunks to a backend running Qwen3-ASR on CPU only, shows the transcript and latency live, handles errors, and measures performance.
All numbers below were measured on the machine described in section 1 unless marked **estimate**. Detailed data and scripts are in `reports/` and `tests/`.

## 1. Hardware and environment
| Item | Value |
|---|---|
| CPU | Intel Core i5-10500H, 6 cores / 12 threads, 2.5 GHz (AVX2) |
| RAM / OS | 24 GB / Windows 11 |
| GPU | GTX 1650 Ti present but **not used** (hidden from PyTorch; CPU-only PyTorch build) |
| Software | Python 3.13, PyTorch 2.15 (CPU), Transformers 5.23, FastAPI 0.163, Node 22, React 19 + Vite |
| Model / runtime | `Qwen/Qwen3-ASR-0.6B-hf`, Hugging Face Transformers, float32, 6 torch threads |

## 2. Approach
- **Architecture:** React UI <-> WebSocket <-> FastAPI backend <-> Qwen3-ASR (diagram: `architecture/architecture.png`). Frontend and backend are separate and talk only through the API and the stream.
- **Audio:** 16 kHz mono 16-bit Linear PCM WAV. The browser parses the WAV header itself (so the format is verified, not silently converted), cuts the PCM into 2 s chunks (64 KB) and sends each when its audio would have been spoken, i.e. at real-time speed. One WebSocket = one call leg.
- **Chunk size:** 2 s. Measured 0.5, 1, 2 and 5 s: 0.5-2 s behave almost identically; 5 s delays the first text by about 4 s (it can only start after the first chunk) but halves the model work.
- **Streaming:** the Transformers model is offline-only (the official streaming mode needs vLLM, not available on Windows/CPU here), so streaming is application-level: the backend buffers chunks and every 2 s of new audio re-transcribes the current segment (partial text, may change);
  a segment is committed at a quiet point once it reaches 10 s so cost per update stays bounded; the final pass runs at the end. Chunk size and processing window are independent.
- **Concurrency control:** one inference at a time by default (a single inference already uses about 6 cores); other streams wait in a queue; a cap on simultaneous streams returns `server_busy`.
- **Errors:** invalid or wrong-format audio, bad messages, unreachable backend, server killed mid-stream, model failure and client disconnects all produce a clear message and clean up (tested).
- **C++ inference:** investigated and measured. Qwen3-ASR-0.6B itself was run in a C++ runtime (transcribe.cpp, GGUF Q5_K_M): offline it is 1.5-2.5x faster and uses about 1/3 of the RAM, but it was worse on Indonesian and was not wired into the streaming backend. I kept Transformers for the application because it was the most accurate on all three languages and integrates directly with the Python backend (section 7). whisper.cpp was benchmarked as a second alternative.

## 3. Latency (single stream, English 11.1 s clip, real-time pacing)
| Measure | Result |
|---|---|
| First transcript after stream start | about 3 s (6 s with a 4 s update interval) |
| Final transcript after the last audio is sent | about 6.5 s |
| Partial lag (audio received but not yet transcribed) | mean 1.3 s, max 3.1 s |
| Real-time factor, whole-clip model time / audio | 1.3 while streaming (the window is re-transcribed); 0.5 for one offline pass |
Dense speech is slower: for a 52 s fast Indonesian conversation the lag reached 10-14 s and the final text arrived about 7-13 s after the end, because compute per second of audio was close to 1.

## 4. CPU and memory (backend process tree)
Model load: about 6 s (cached), CPU peak about 1000%, RAM rising to 3.6 GB. Idle: about 0% CPU, 3.6 GB. One stream: about 6 busy cores (peak about 610%), 3.8 GB. Six streams: 3.9-4.0 GB (the first stream adds about 200 MB, each further one about 15 MB).
CPU, not memory, is the limit.

## 5. Accuracy (own recordings; reference text typed by the speaker; lowercase, punctuation removed; CER ignores spaces)
| Clip | Metric | Offline | Streaming |
|---|---|---|---|
| English, 11 s | WER | 0.353 | 0.353 |
| Mandarin, 16 s | CER | 0.000 | 0.000 |
| Indonesian, 52 s casual conversation | WER | 0.442 | 0.363-0.469 |
WER counts only word differences: English errors are almost entirely the name "Qwen3-ASR" ("Q and three"); Indonesian errors mix real misrecognitions with informal spellings ("enggak" vs "nggak").
Three short clips from one speaker, so this shows the pipeline works but is not a general benchmark.

## 6. Concurrency (N simultaneous real-time streams; English and Mandarin clips)
Acceptable = no failures, worst final latency <= 10 s, average lag <= 5 s (my assumption).
| Streams | Worst final latency (default) | Queue wait total | CPU (process avg) | RAM | Result |
|---:|---:|---:|---:|---:|---|
| 1 | 6.5 s | 0 s | 428% | 3.8 GB | OK |
| 2 | 11.7 s (7.7-7.8 s with 4 s updates or 2 inferences x 3 threads) | 18 s | 499% | 3.8 GB | OK only in the tuned settings |
| 3 | 18.6 s | 45 s | 523% | 3.8 GB | over limit |
| 6 | 35.7 s | 192 s | 547% | 3.9 GB | over limit |
No stream failed at any level; the system slows down instead of breaking. Accuracy did not change under load.
**Measured capacity of this machine: 1 stream with default settings, 2 with tuning.**

## 7. Alternatives and quantization
| Option | Result (measured) |
|---|---|
| **Qwen3-ASR-0.6B in transcribe.cpp (C++, GGUF Q5_K_M, CPU)** | same model as the app, offline whole-file, 6 threads. English 3.0-3.2 s, WER 0.294; Mandarin 3.6-3.8 s, CER 0.000; Indonesian 17.6-18.0 s, WER **0.602 (worse than Transformers' 0.442)**. RAM 1.2-1.3 GB vs 3.6-3.8 GB, i.e. about 1.5x (short clips) to 2.5x (52 s clip) faster. Cause of the Indonesian drop not isolated (5-bit quantization or decoding; Q8_0 not run). Built from source (the Windows release has DLLs only). Streaming not tested. |
| whisper.cpp small (C++) | about as fast as Qwen on short clips, about 3x faster on the dense Indonesian clip, RAM 0.8-0.9 GB; English WER 0.235 (better), Mandarin 0.000, Indonesian 0.522 (worse than Qwen's 0.442) |
| whisper.cpp base 5-bit | fastest (RTF 0.15-0.26), RAM 0.2-0.3 GB, but Indonesian WER 0.70 |
| whisper.cpp large-v3-turbo 5-bit | slow (RTF 1.5-2) and it failed on the long Indonesian clip (10 of 121 words) with default settings |
| Qwen bfloat16 | about 6x slower (no native bf16 on this CPU) |
| Qwen int8 dynamic quantization | 15% faster on short clips, 2.3x slower and less accurate on the long clip |
| 5-bit whisper models | about 60% smaller, no accuracy loss on these clips, but not faster |
Researched, not run: CrispASR (another Qwen3-ASR C++ runtime), the official `qwen-asr` package on CPU, vLLM streaming (WSL2), faster-whisper int8, sherpa-onnx streaming models. Next test: transcribe.cpp with Q8_0 (to isolate the Indonesian accuracy drop) and its streaming behaviour.
Three clips from one speaker, so these rankings are indicative only. Details: `reports/phase7_findings.md`, data: `reports/transcribe_cpp_results.csv`.

## 8. Capacity estimates (estimates, not measurements; assumptions in `reports/capacity_estimates.md`)
Basis: one 12-vCPU worker (one model process) serves 2 calls (best measured), 30% headroom, linear scaling, 4 workers per 48 vCPU / 32 GB node.
| Call legs | Workers | vCPU | RAM | Servers (48 vCPU / 32 GB) |
|---:|---:|---:|---:|---:|
| 50 | 33 | 396 | 132 GB | 9 |
| 100 | 65 | 780 | 260 GB | 17 |
| 200 | 130 | 1,560 | 520 GB | 33 |
| 500 | 325 | 3,900 | 1,300 GB | 82 |
| 1,000 | 650 | 7,800 | 2,600 GB | 163 |
If a future optimisation (native or incremental streaming, silence skipping) really gave 2.5x the capacity per worker, the 1,000-call figure would fall to about 260 workers / 65 servers; this is a hypothesis, not a result.

## 9. Scaling the design
Measured bottleneck: CPU for inference. Proposed design (`architecture/scaling.png`): load balancer with sticky WebSocket streams -> stateless gateways that hold the sockets and cut audio into jobs -> a job queue with admission control -> a pool of CPU ASR workers (one model each, pinned cores), autoscaled on queue wait.
Also reduce work per call: native/incremental streaming, silence skipping, a faster runtime. Not built.

## 10. Limitations
- Application-level streaming (partial text can change); lag on dense speech; low concurrency on a laptop CPU.
- Small test set (3 short clips, one speaker, plus clean synthetic clips); single runs for most timings; thermal throttling and background load were not controlled.
- Load test used English/Mandarin clips only; calls started within 2 s of each other; latency thresholds are my own assumption.
- Windows only; no authentication/TLS; no microphone input.
- Sizing numbers for 50-1000 calls are estimates and probably optimistic about linear scaling.

## 11. Conclusions
Qwen3-ASR-0.6B runs on a CPU-only machine and transcribes English, Mandarin and Bahasa Indonesia, and the end-to-end system (UI, streaming backend, error handling, measurements) works and is tested.
Its cost on CPU is high: one stream occupies about six cores, so capacity is roughly 1-2 calls per such machine, and CPU compute is what a larger deployment must scale.
Two levers cut cost: removing repeated re-transcription, and a faster runtime. The same Qwen3-ASR model in a C++ runtime (transcribe.cpp, Q5_K_M) was 1.5-2.5x faster with about a third of the RAM offline, so Transformers is the most accurate and easiest to integrate choice here, **not** the fastest or lightest. Its Indonesian accuracy was worse (0.602 vs 0.442), so switching would need a Q8_0 check first. A smaller Whisper model is another cheaper option with different accuracy trade-offs per language (better on English, worse on Indonesian in these tests).
The sizing table in section 8 is based on the Transformers measurements; a C++ runtime could lower it, but that was not measured under streaming load.
Next steps: run transcribe.cpp Q8_0 and test it with streaming, add silence skipping, and re-measure on larger, more varied audio.
