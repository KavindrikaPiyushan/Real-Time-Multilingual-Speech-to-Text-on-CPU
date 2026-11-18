# Phase 1 findings: environment, research, CPU smoke test

## 1. Test environment (measured/recorded)
| Item | Value |
|---|---|
| CPU | Intel Core i5-10500H @ 2.5 GHz, 6 cores / 12 threads |
| RAM | 24 GB |
| GPU | NVIDIA GTX 1650 Ti present but **not used** (`CUDA_VISIBLE_DEVICES=""`, CPU-only torch build; `torch.cuda.is_available()` = False) |
| OS | Windows 11 Home |
| Python / Node | 3.13.1 / 22.14.0 |
| Key packages | torch 2.15.0+cpu, transformers 5.23.0, soundfile 0.14.0, soxr, psutil 7.2.2, jiwer 4.0.0 (full list: `backend/requirements-phase1.txt`) |
| Model / runtime | `Qwen/Qwen3-ASR-0.6B-hf`, Hugging Face Transformers, CPU, float32 |
| Torch threads | 6 (default) |

## 2. Research summary
- Model structure, backends, sizes and streaming: see `docs/notes/qwen3-asr.md`.
- CPU compatibility of each runtime option: see `docs/notes/cpu-compat.md`.

## 3. Smoke test result (`tests/phase1_smoke.py`, sample `samples/english.wav`)
Audio: 11.10 s, 16 kHz, mono, PCM_16 (converted from a stereo recording with ffmpeg).

| Metric | Result |
|---|---|
| Model load (cached, 2 runs) | 6.5 s and 5.6 s |
| First-time load incl. download | about 612 s (one-off, mostly download) |
| RAM after load | about 3.58 GB (process RSS) |
| Peak RSS during inference | about 3.8 GB |
| Inference time, warm | about 5.9 s (5.89, 5.96, 5.92) |
| Inference time, first run after start | 12.25 s in one session (see note) |
| Real-time factor (RTF), warm | about 0.53 |
| Process CPU during inference | about 580-600% (about 6 cores busy) |

Transcript produced (identical in all four runs):
> The release Q and three is a family that includes two powerful all-in-one speech recognition models that support language identification.

Notes:
- The first run in the first session (12.25 s, RTF 1.10) was slower. This was only seen in the first session, where the run came right after the first model load, so I treat it as warm-up or first-use cost. The second session's first run was 5.96 s. This is an observation, not a proven cause.
- RTF is processing time / audio duration for one complete 11.1 s clip on an otherwise idle machine. It is a single-stream, offline measurement; it does not yet say anything about real-time streaming or concurrency.
- CPU % is per-process and can exceed 100% (6 busy cores is about 600%). The machine has 12 logical processors.
- Accuracy: the sample is not yet scored. **[TO DO]** write the reference text of what was spoken and compute WER in Phase 6. The model appears to have mis-recognised the spoken product name ("Qwen3-ASR" came out as "Q and three"), which suggests names and acronyms are a weak point. Confirm against the real reference first.

## 4. Conclusions and decision
- Qwen3-ASR-0.6B-hf **loads and transcribes on this CPU** with no GPU: Phase 1's first priority is met.
- Single-stream speed (RTF about 0.53 with all 6 threads) is faster than real time, but it uses most of the CPU. Concurrency will likely be limited: each extra stream competes for the same cores. This must be tested in Phase 6, not assumed.
- Memory per model instance is about 3.6-3.8 GB in float32. Multiple processes each holding a model would multiply this.
- Decision: use Transformers on CPU with **application-level chunked streaming** (native streaming is vLLM-only; see the CPU-compat notes).

## 5. Next steps / ideas to test in Phase 2
- Run on Mandarin and Bahasa Indonesia samples.
- Try bfloat16 and fewer torch threads, and compare time and quality.
- Time encoder vs generate to see where the time goes.
- Test short windows (2-5 s) to see the cost per window, which determines how often partial updates are affordable.
