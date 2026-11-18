# Phase 7 findings: alternatives, quantization and scaling

Same machine and clips as before (i5-10500H 6C/12T, 24 GB, Windows 11, CPU only; English 11 s, Mandarin 16 s, Indonesian 52 s, own recordings).
Everything marked **measured** was run here; everything marked **researched** comes from documentation/web sources and was not run by me.

## 1. whisper.cpp vs Qwen3-ASR (measured, offline whole-file, language forced, 6 threads)
whisper.cpp v1.9.2 prebuilt Windows CPU binary (`whisper-cli`), models from the official `ggerganov/whisper.cpp` Hugging Face repo.
Whisper time = wall clock of a fresh process (includes about 0.3-1 s model loading). Qwen time = inference only, model already loaded.
Two repeats per cell (timings repeated within 1 s). Data: `whisper_cpp_results.csv`, `accuracy_results.csv`, `qwen_quantization_results.csv`.

| Model (file size) | English 11 s: time, WER | Mandarin 16 s: time, CER | Indonesian 52 s: time, WER | Process RAM |
|---|---|---|---|---|
| **Qwen3-ASR-0.6B**, Transformers float32 | 4.8-5.9 s, 0.353 | 4.9-6.9 s, 0.000 | 44-45 s, 0.442 | 3.6-3.8 GB |
| whisper small (488 MB) | 5.6 s, 0.235 | 5.6 s, 0.000 | 15.4 s, 0.522 | 0.8-0.9 GB |
| whisper small 5-bit q5_1 (190 MB) | 6.1 s, 0.176 | 6.1 s, 0.000 | 18.7 s, 0.522 | 0.5-0.6 GB |
| whisper base 5-bit q5_1 (60 MB) | 2.0 s, 0.235 | 2.3 s, 0.000 | 13.6 s, 0.699 | 0.2-0.3 GB |
| whisper large-v3-turbo 5-bit q5_0 (574 MB) | 23 s, 0.118 | 24 s, 0.000 | 45.7 s, **0.956 (failed)** | 0.85 GB |

- **Speed:** whisper small is about as fast as Qwen on the short clips and about 3x faster on the dense Indonesian clip, with about a quarter of the RAM.
  whisper base is the fastest (RTF about 0.15-0.26) but clearly less accurate on Indonesian. large-v3-turbo q5_0 was slow here (RTF 1.5-2.1 on short clips).
- **Accuracy depends on the language:** English - whisper small/turbo beat Qwen (0.12-0.24 vs 0.35); Mandarin - all models perfect on this sample;
  Indonesian - Qwen was best (0.442 vs 0.52 for small, 0.70 for base). Turbo transcribed only 10 of 121 words of the long Indonesian clip, on both runs
  (stopped early after repeating the first phrase), so its 0.956 is a failure to transcribe the whole clip, not a word-accuracy result; I used default CLI
  settings and did not investigate the cause.
- The product name "Qwen3-ASR" was misrecognised by every model except (nearly) turbo ("Gwentry ASR"): out-of-vocabulary names are a general weak point.
- Three clips from one speaker: ranking is indicative, not a benchmark. Differences of a few WER points are within noise.
- **Integration effort:** whisper.cpp runs as a standalone executable (`whisper-cli`, and `whisper-server` for HTTP) - no Python, small install, but it is an
  offline decoder: it would still need the same application-level chunking for streaming. Qwen via Transformers needs a Python/PyTorch stack (about 3.6 GB RAM).
- **Streaming:** neither was run as a true streaming decoder here.

## 2. Quantization / precision (measured, Qwen3-ASR in PyTorch on this CPU)
| Variant | English 11 s | Mandarin 16 s | Indonesian 52 s | Verdict |
|---|---|---|---|---|
| float32 (baseline) | 4.8 s, WER 0.353 | 4.9 s, CER 0.000 | 44 s, WER 0.442 | reference |
| bfloat16 | 29.6 s (RTF 2.7) | 40.0 s | 145 s | **about 6x slower** (this CPU has no native bf16); RAM 2.9 GB |
| int8 dynamic (torch `quantize_dynamic` on Linear layers) | 4.0 s, WER 0.294 | 4.5 s, CER 0.000 | **103 s, WER 0.575** | 15% faster on short clips, 2.3x slower and less accurate on the long one |
- On this hardware neither option is a win. float32 stays the best choice; reduced precision only helps when the CPU supports it (e.g. AVX512-BF16/VNNI or a runtime with optimised kernels).
- The 7.2 GB RAM seen for int8 is an artefact of my script (quantized and original copies in one process), not the real int8 footprint.
- In whisper.cpp, 5-bit quantization cut model size by about 60% (488 -> 190 MB) and RAM by about 30%, with no accuracy loss on these clips, but it was **not faster**
  (6.1 s vs 5.6 s English, 18.7 s vs 15.4 s Indonesian). Quantization saved memory and disk, not time, on this CPU. (Researched: another user's benchmark on old hardware also found 5-bit formats slower than 4-bit/8-bit.)
- Not tested: GGUF-quantized Qwen3-ASR in a C++ runtime (see section 3).

## 3. Other CPU options (researched, not run)
| Option | What it is | Why it might help | Risk / unknown |
|---|---|---|---|
| Qwen3-ASR in C++ (CrispASR, transcribe.cpp, RapidSpeech.cpp; GGUF quantized) | ggml-based runtimes that load Qwen3-ASR | Keeps the required model, matches the "C++ preferred" note, smaller RAM; one report claims faster than real time on a 4-core Xeon | Self-reported numbers, young projects; streaming support and Windows builds not verified by me |
| vLLM backend (official Qwen3-ASR streaming) | native incremental streaming | Removes the repeated re-transcription that costs this design about 2.5x extra compute | No native Windows; CPU support for Qwen3-ASR not confirmed (WSL2 untested) |
| faster-whisper (CTranslate2, int8) | Python wrapper with optimised int8 CPU kernels | Often faster than whisper.cpp on x86 CPUs | Not tested here |
| sherpa-onnx streaming models | true streaming recognisers (ONNX) | Designed for low-latency CPU streaming, very low compute | Language coverage (Indonesian in particular) and accuracy unverified |
| GPU serving | any model on a GPU | Large throughput gain | Outside the assignment's CPU-only constraint |

## 4. Where the time goes, and how to scale (reasoning from the measurements)
Measured facts: one stream uses about 6 cores; capacity of this 6C/12T machine was 2 streams within my latency criteria (1 with defaults);
RAM is not the limit (3.6 GB shared model, about 15 MB per extra stream); streaming costs about 2.5-3x more compute than one offline pass
(English: 14 s of model time vs 5 s offline), because each update re-transcribes the current window.

Ordered by expected effect (estimates, not measured unless stated):
1. **Cut redundant compute:** native/incremental streaming (vLLM or a C++ streaming runtime), or longer update intervals (measured: 4 s updates cut compute about 25% at the cost of +3 s first text).
2. **Use a cheaper model where accuracy allows:** whisper small was 3x faster than Qwen on the dense clip (measured), at some accuracy cost for Indonesian. A per-language model choice is possible.
3. **Skip silence (voice activity detection):** phone calls contain pauses; not measured here, so the saving is unknown.
4. **Scale out by processes and machines:** one model process per set of cores (pinning avoids cores fighting), a WebSocket-aware load balancer, sticky streams, and a queue with admission control so an overloaded node rejects new calls instead of slowing existing ones (the server already has a stream cap and returns `server_busy`).
5. **Autoscale on queue wait / lag**, which my load test showed is the first signal to degrade (queue wait grew from 0 s to about 190 s total at 6 streams).
6. **Separate the layers:** stateless WebSocket gateways that buffer and forward audio, and a pool of ASR workers behind a queue, so the model tier can be scaled independently.

## 5. What I would test next
Qwen3-ASR GGUF in a C++ runtime (speed, RAM, accuracy, streaming); faster-whisper int8; a VAD in front of the model; the whisper-turbo long-audio failure with different settings;
a larger and more varied test set (several speakers, noisy phone audio) before drawing accuracy conclusions.
