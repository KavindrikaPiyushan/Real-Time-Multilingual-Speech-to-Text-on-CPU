# Phase 2 findings: standalone ASR on three languages (CPU)

Setup: see `phase1_findings.md` (i5-10500H, 6C/12T, 24 GB, Windows 11, Qwen3-ASR-0.6B-hf, Transformers, float32, CPU-only).
Code: `backend/app/services/audio_service.py` (WAV validation/loading), `backend/app/services/asr_service.py` (model + transcribe),
`tests/phase2_transcribe.py` (runner). Raw results: `reports/phase2_results.csv`. Model load 7.2 s, RAM 3.58 GB.

## Results (one run each, idle machine)
| Sample | Source | Mode | Audio | Infer | RTF | Error |
|---|---|---|---:|---:|---:|---|
| english.wav | my own recording | auto-detect (English detected) | 11.1 s | 8.44 s | 0.76 | not scored (no reference yet) |
| english.wav | my own recording | forced English | 11.1 s | 6.12 s | 0.55 | not scored |
| mandarin_tts.wav | **synthetic TTS** (edge-tts, Xiaoxiao) | auto-detect (Chinese detected) | 8.7 s | 5.60 s | 0.64 | CER 0.000 |
| mandarin_tts.wav | synthetic TTS | forced Chinese | 8.7 s | 5.12 s | 0.59 | CER 0.000 |
| indonesian_tts.wav | **synthetic TTS** (edge-tts, Gadis) | auto-detect (Indonesian detected) | 12.3 s | 8.20 s | 0.67 | WER 0.000 |
| indonesian_tts.wav | synthetic TTS | forced Indonesian | 12.3 s | 7.97 s | 0.65 | WER 0.000 |

## Observations
- All three languages transcribe on CPU, and language auto-detection picked the right language each time.
- RTF was 0.55-0.76 for single streams (faster than real time, but uses most of the CPU).
- Inference time varies between runs (English auto 8.4 s vs forced 6.1 s on the same audio), so the numbers need repetition. Do not read a difference
  between auto and forced from one run.
- Inputs are validated (16 kHz mono required in strict mode); non-WAV or unreadable files raise a clean `AudioError`.

## Limits of these results (important)
- Mandarin and Indonesian clips are **clean synthetic speech**, so 0% error is not representative of real call audio. Replace with real
  recordings before reporting accuracy.
- The English sample has no reference transcript yet, so no WER.
- One run per sample: timings are indicative only. Phase 6 should repeat and average.
- Reference normalisation used by the runner: lowercase, punctuation removed; CER ignores spaces.
