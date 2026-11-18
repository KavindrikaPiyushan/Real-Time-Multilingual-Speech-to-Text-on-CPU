# Phase 2 findings: standalone ASR on three languages (CPU)

Setup: see `phase1_findings.md` (i5-10500H, 6C/12T, 24 GB, Windows 11, Qwen3-ASR-0.6B-hf, Transformers, float32, CPU-only).
Code: `backend/app/services/audio_service.py` (WAV validation/loading), `backend/app/services/asr_service.py` (model + transcribe),
`tests/phase2_transcribe.py` (runner). Raw results: `reports/phase2_results.csv`. Model load 7.2 s, RAM 3.58 GB.

## Results (one run each, idle machine; model load 6.5 s, RAM 3.58 GB)
| Sample | Source | Audio | Mode | Infer | RTF | Error |
|---|---|---:|---|---:|---:|---|
| english.wav | real recording | 11.1 s | auto / forced | 6.05 s / 5.88 s | 0.55 / 0.53 | WER 0.353 |
| mandarin.wav | real recording | 15.7 s | auto / forced | 6.86 s / 6.44 s | 0.44 / 0.41 | not scored (no reference yet) |
| indonesian.wav | real recording (casual conversation) | 52.2 s | auto / forced | 45.96 s / 41.70 s | 0.88 / 0.80 | not scored (no reference yet) |
| mandarin_tts.wav | synthetic TTS | 8.7 s | auto / forced | 4.71 s / 4.26 s | 0.54 / 0.49 | CER 0.000 |
| indonesian_tts.wav | synthetic TTS | 12.3 s | auto / forced | 7.20 s / 6.75 s | 0.59 / 0.55 | WER 0.000 |

Language auto-detection picked the right language for all five clips.

## Observations
- **English WER 0.353 is almost entirely one phrase.** Reference: "They released Qwen3-ASR, a family ..."; output: "The release Q and three is a family ...".
  The product name and its neighbours (They released / The release) account for the errors; the rest of the sentence is correct.
  The reference-normalisation step (lowercase, strip punctuation) cannot fix a name that the model heard as separate words.
- **RTF grows with clip length:** about 0.4-0.55 for 11-16 s clips but 0.80-0.88 for the 52 s clip. Longer audio costs more time per second
  (more encoder frames and more output tokens). **Design implication:** re-transcribing an ever-growing buffer will get slower as a call goes on,
  so the streaming design needs a bounded or sliding window. This is a single measurement; confirm it in Phase 6.
- Single-stream RTF is below 1 everywhere but uses about 6 cores, so concurrent streams will be the limiting factor.
- Timing varies a little between runs; do not read auto-vs-forced differences from single runs.
- Mandarin (real) transcript looks plausible ("你叫什么名字？你来自哪里？..."), pending a reference.
- Indonesian (real) is fast casual speech; the output has some clear misrecognitions (e.g. "sedibetnya", "tempet"), but this needs a human reference to quantify.
- Inputs are validated (strict mode requires 16 kHz mono; unreadable or non-WAV files raise a clean `AudioError`).

## Limits and to-do
- **Need references** for `mandarin.wav` and `indonesian.wav` (what was actually said) in `samples/references/mandarin.txt` and `indonesian.txt`.
- TTS clips are clean synthetic speech: 0% error there is not representative. Keep them only as a sanity check.
- One run per sample. Phase 6 should repeat and average.
- Normalisation used: lowercase, punctuation removed; CER ignores spaces. Code: `tests/phase2_transcribe.py`.
