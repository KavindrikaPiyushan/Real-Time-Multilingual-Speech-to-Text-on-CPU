# CPU compatibility investigation (Phase 1, Step 5)

Test machine: Intel Core i5-10500H (6 cores / 12 threads), 24 GB RAM, Windows 11, Python 3.13.1.
GPU (GTX 1650 Ti) is NOT used; CPU-only torch build installed (`torch 2.15.0+cpu`).
Legend: **[VERIFIED]** = I ran it on this machine. **[RESEARCHED]** = from docs/web, not run here. **[TO TEST]** = not done yet.

## Summary table

| Option | Route | Runs on CPU here? | Streaming? | Status |
|---|---|---|---|---|
| A | Transformers + `Qwen/Qwen3-ASR-0.6B-hf` | Expected yes | No (app-level only) | Env installed [VERIFIED]; model run **[TO TEST in Step 6]** |
| B | `qwen-asr` package, Transformers backend | Installs on Windows/CPU [VERIFIED dry-run]; run **[TO TEST]** | No | Needs its own venv (see conflict below) |
| C | `qwen-asr` + vLLM (official streaming) | Unlikely on native Windows | Yes (native) | [RESEARCHED] not practical; WSL2 route unverified |
| D | C++/ggml runtimes (CrispASR, transcribe.cpp, others) | Yes per their docs | Varies | [RESEARCHED]; candidate for Phase 7 and the "C++ preferred" requirement |

## Option A: Transformers `-hf` on CPU (baseline)
- `pip` environment in `backend/.venv` has: torch 2.15.0+cpu, transformers 5.23.0 (needs >= 5.13.0), accelerate, soundfile, numpy, psutil, jiwer. [VERIFIED]
- Model load and inference not yet run. Done in Step 6 with `tests/phase1_smoke.py`.
- Expected limits: float32 on CPU is memory-heavy and slowish; try bfloat16 if needed. [TO TEST]

## Option B: `qwen-asr` package (official, Transformers backend)
- `pip install --dry-run qwen-asr` in a throwaway Python 3.13 venv resolved successfully on Windows with CPU torch:
  qwen-asr 0.0.6, **transformers 4.57.6**, gradio, librosa, etc. [VERIFIED]
- **Dependency conflict:** qwen-asr pins transformers 4.57.6, while the `-hf` model needs transformers >= 5.13.0.
  They cannot share one environment. If B is tested, use a separate venv (e.g. `.venv-qwenasr`) and keep the main backend on Option A.
- All official examples use `device_map="cuda:0"`; CPU use is undocumented. [RESEARCHED] Would need `device_map="cpu"` and float32. [TO TEST]
- Value of B: it is the official API, but A is already native in Transformers, so B is only a fallback or comparison.

## Option C: vLLM backend (official streaming)
- Streaming in Qwen3-ASR is documented only for the vLLM backend (no batch inference, no timestamps). [RESEARCHED, README]
- vLLM does not support native Windows; the official guidance is WSL2 (Linux). vLLM's CPU backend needs x86_64 with AVX2 minimum (AVX512 preferred).
  My CPU is Comet Lake (AVX2, no AVX512), so it would meet the minimum. [RESEARCHED]
- `wsl -l -v` on this machine shows only the `docker-desktop` distro (stopped), so a normal Linux distro (e.g. Ubuntu) would have to be installed first. [VERIFIED]
- No source confirms that Qwen3-ASR's streaming mode works on vLLM's CPU backend. The official examples target CUDA. [RESEARCHED]
- Conclusion: **not practical for the main submission.** Optional stretch: install Ubuntu in WSL2 and try; document the result either way.

## Option D: C++/ggml runtimes for Qwen3-ASR (relevant to "C++ preferred")
Found by web search; claims are the projects' own and **not verified by me**:
- **CrispASR**: ggml-based C++ runtime with Qwen3-ASR; a community report claims faster-than-real-time on a 4-core Xeon, with GGUF quantisation.
- **transcribe.cpp**: GGUF conversions of Qwen3-ASR 0.6B and 1.7B (e.g. 0.6B Q5_K_M about 707 MB; self-reported 2.21% LibriSpeech test-clean WER).
- **RapidSpeech.cpp**, **chatllm.cpp** community quantisations, and a Rust CPU implementation (`qwen-asr` crate) with a streaming API.
- Mainline llama.cpp native support for Qwen3-ASR was **not confirmed**.
- Value: this is the likely answer to "C++ inference option". Test in Phase 7 on the same samples and compare latency, RAM and accuracy against Option A.

## Decision (so far)
1. Main implementation: **Option A** (Transformers, `Qwen3-ASR-0.6B-hf`, CPU) with **application-level chunked streaming**.
2. Do not rely on native vLLM streaming; document why (Windows unsupported, CPU unverified, WSL2 untested).
3. Phase 7: test one C++ runtime (transcribe.cpp or CrispASR) against Option A, plus whisper.cpp as the required alternative.
4. Final status of A depends on Step 6; update this file after it.

## Sources
- Qwen3-ASR README: https://github.com/QwenLM/Qwen3-ASR
- vLLM installation docs (Windows via WSL): https://docs.vllm.ai/getting_started/installation/gpu.html
- vLLM CPU package page: https://pypi.org/project/vllm-cpu/0.17.1/
- CrispASR discussion: https://huggingface.co/Qwen/Qwen3-ASR-0.6B/discussions/12
- transcribe.cpp 0.6B GGUF: https://huggingface.co/handy-computer/Qwen3-ASR-0.6B-gguf
- Rust CPU crate: https://lib.rs/crates/qwen-asr
