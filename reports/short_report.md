# Short Report: Real-Time Multilingual Speech-to-Text on CPU

Candidate project for the Tetherfi Fresher Technical Assignment. Everything below was **measured** on the machine in section 1 unless marked **(estimate)**. Full data, scripts and the longer write-up are in `reports/technical_report.md` and `reports/`.

## 1. Hardware
| Item | Value |
|---|---|
| CPU | Intel Core i5-10500H, 6 cores / 12 threads, 2.5 GHz (AVX2) |
| RAM / OS | 24 GB / Windows 11 |
| GPU | Present but **not used** (CPU-only PyTorch build) |
| Model / runtime | Qwen3-ASR-0.6B (`Qwen/Qwen3-ASR-0.6B-hf`), Hugging Face Transformers, PyTorch CPU, float32, 6 threads |
| Stack | React 19 + Vite (UI), FastAPI + WebSocket (backend), Python 3.13 |

## 2. Approach
- **Architecture:** React UI <-> WebSocket <-> FastAPI backend <-> Qwen3-ASR. UI and backend are separate and communicate only through the API/stream (diagrams: `architecture/architecture.png`, `architecture/scaling.png`).
- **Audio:** 16 kHz mono 16-bit PCM WAV. The browser reads the WAV header, cuts the audio into **2 s chunks (64 KB)** and sends each at real-time speed. One WebSocket = one call leg.
- **Why 2 s:** I tested 0.5, 1, 2 and 5 s. 0.5–2 s behave almost the same; 5 s delays the first text by about 4 s. 2 s keeps messages few while keeping text appearing quickly.
- **Streaming:** The Transformers model only works on complete audio, so streaming is done in the application: every 2 s of new audio the backend re-transcribes the current segment (partial text, may change). A segment is committed at a quiet point once it reaches 10 s, to bound the cost. A final pass runs at the end.
- **Concurrency control:** one inference at a time (one inference already uses about 6 cores); other streams queue; a cap on streams returns `server_busy`.
- **Errors handled:** invalid or wrong-format audio, bad messages, backend unreachable, server killed mid-stream, model failure, client disconnect.
- **C++ option:** I ran the same model in a C++ runtime (transcribe.cpp, GGUF Q5_K_M) and also whisper.cpp. See section 7.

## 3. Latency (single stream, English 11.1 s clip)
| Measure | Result |
|---|---|
| First text after stream start | about 3 s |
| Final transcript after last audio sent | about 6.5 s |
| Partial lag (audio received, not yet transcribed) | mean 1.3 s, max 3.1 s |
| Real-time factor | 1.3 while streaming (window re-transcribed); 0.5 for one offline pass |

Dense speech is slower: for a 52 s fast Indonesian conversation the lag reached 10–14 s and final text arrived 7–13 s after the end.

## 4. CPU and memory
- Model load about 6 s (cached); idle about 0% CPU, 3.6 GB RAM.
- One stream: about 6 busy cores (peak about 610%), 3.8 GB.
- Six streams: 3.9–4.0 GB. The first stream adds about 200 MB, each further stream about 15 MB.
- **CPU, not memory, is the limit.**

## 5. Accuracy (my own recordings, reference typed by the speaker; lowercase, no punctuation)
| Clip | Metric | Offline | Streaming |
|---|---|---|---|
| English, 11 s | WER | 0.353 | 0.353 |
| Mandarin, 16 s | CER | 0.000 | 0.000 |
| Indonesian, 52 s conversation | WER | 0.442 | 0.363–0.469 |

English errors are almost all the name "Qwen3-ASR". Indonesian errors mix real misrecognitions and informal spellings ("enggak" vs "nggak"). Three short clips from one speaker: this shows the pipeline works, it is not a general benchmark.

## 6. Concurrency test (N simultaneous real-time streams)
"Acceptable" = no failures, worst final latency <= 10 s, average lag <= 5 s (my own threshold).
| Streams | Worst final latency | CPU (avg) | RAM | Result |
|---:|---:|---:|---:|---|
| 1 | 6.5 s | 428% | 3.8 GB | OK |
| 2 | 11.7 s (7.7 s with tuning) | 499% | 3.8 GB | OK only with tuning |
| 3 | 18.6 s | 523% | 3.8 GB | over limit |
| 6 | 35.7 s | 547% | 3.9 GB | over limit |

No stream failed; the system slows down instead of breaking. **Measured capacity of this machine: 1 stream with default settings, 2 with tuning.**

## 7. Alternatives and research
| Option | Result (measured) |
|---|---|
| Qwen3-ASR-0.6B in transcribe.cpp (C++, Q5_K_M) | 1.5–2.5x faster than Transformers, RAM 1.2–1.3 GB vs 3.6–3.8 GB. English WER 0.294, Mandarin CER 0.000, but Indonesian WER **0.602 (worse than 0.442)**. Offline only; streaming not tested. |
| whisper.cpp small | about as fast as Qwen on short clips, about 3x faster on dense Indonesian, RAM 0.8–0.9 GB. English WER 0.235, Mandarin 0.000, Indonesian 0.522. |
| whisper.cpp base (5-bit) | fastest (RTF 0.15–0.26), RAM 0.2–0.3 GB, but Indonesian WER 0.70. |
| Qwen int8 / bfloat16 | no useful gain on this CPU (bfloat16 about 6x slower). |

Answers to the assignment's questions:
- **Better or worse?** C++ runtimes are faster and lighter, but accuracy differs by language. Whisper small was better on English and worse on Indonesian; transcribe.cpp (Q5_K_M) was worse on Indonesian. I kept Transformers because it was the most accurate on all three languages and integrates directly with the Python backend.
- **Less CPU or memory?** Memory: yes, clearly (0.2–1.3 GB vs 3.6–3.8 GB). CPU: not measured as a percentage; inferred from shorter run times.
- **Easier to run in real time?** They finish faster than real time offline, but I did not test either one streaming, so this is not proven.
- **Multilingual support?** Both handled all three languages, with the accuracy differences above.
- **Test next:** transcribe.cpp with Q8_0 (to find whether the Indonesian drop is from quantization) and its streaming behaviour; also faster-whisper int8 and sherpa-onnx streaming models (researched, not run).

## 8. Sizing estimates
**Only the 1–6 stream rows in section 6 were measured. Everything below is an estimate.**
Assumptions: one 12-vCPU worker (one model process) serves 2 calls (best measured result), 30% headroom, linear scaling, 4 workers per 48 vCPU / 32 GB server.

| Call legs | Workers | vCPU | RAM | Servers (48 vCPU / 32 GB) |
|---:|---:|---:|---:|---:|
| 50 | 33 | 396 | 132 GB | 9 |
| 100 | 65 | 780 | 260 GB | 17 |
| 200 | 130 | 1,560 | 520 GB | 33 |
| 500 | 325 | 3,900 | 1,300 GB | 82 |
| 1,000 | 650 | 7,800 | 2,600 GB | 163 |

If a future optimisation (native streaming, silence skipping) gave 2.5x capacity per worker, 1,000 calls would need about 260 workers / 65 servers. This is a hypothesis, not a result.

**Scaling design (not built):** WebSocket-aware load balancer -> stateless gateways holding the sockets -> job queue with admission control -> autoscaled pool of CPU ASR workers (one model each, pinned cores). Also reduce work per call: incremental streaming, silence skipping, a faster runtime.

## 9. Limitations
- Application-level streaming: partial text can change; lag on dense speech; low concurrency on a laptop CPU.
- Small test set (3 short clips, one speaker); most timings are single runs; thermal throttling and background load not controlled.
- Load test used English and Mandarin clips only; calls started within 2 s of each other; latency thresholds are my own assumption.
- Windows only; no authentication/TLS; no microphone input.
- Sizing for 50–1,000 calls is estimated and probably optimistic because it assumes linear scaling.

## 10. Conclusions
Qwen3-ASR-0.6B runs on CPU only and transcribes English, Mandarin and Bahasa Indonesia. The end-to-end system (UI, streaming backend, error handling, measurements) works and is tested. The cost is high: one stream uses about six cores, so this laptop handles 1–2 calls, and a larger deployment must scale CPU compute. The two biggest levers are removing repeated re-transcription and using a faster runtime (the C++ build was 1.5–2.5x faster with a third of the RAM, but needs an accuracy check on Indonesian first). Next steps: test transcribe.cpp Q8_0 with streaming, add silence skipping, and re-measure on larger, more varied audio.
