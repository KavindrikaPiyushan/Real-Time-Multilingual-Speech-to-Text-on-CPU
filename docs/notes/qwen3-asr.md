# Qwen3-ASR notes (Phase 1, Step 4)

Sources: Qwen3-ASR GitHub README, Hugging Face model cards (`Qwen/Qwen3-ASR-0.6B`, `-0.6B-hf`),
Qwen3-ASR Technical Report (arXiv:2601.21337). Items marked **[TO VERIFY]** are my reasoning, not stated by the sources.

## 1. What ASR is and how Qwen3-ASR works
ASR (Automatic Speech Recognition) turns spoken audio into text. Qwen3-ASR has three parts:
1. **Audio encoder (AuT).** Audio is converted to 128-dim filterbank features and downsampled 8x,
   giving about 12.5 feature vectors per second of audio. The encoder reads them with an attention window
   (1-8 s) and outputs a compact sequence that represents what was said.
   Size: about 180M parameters in the 0.6B model, 300M in the 1.7B model.
2. **Projector.** Maps the encoder output into the language model's input space (the report gives no detail).
3. **LLM decoder.** A Qwen3 language model (Qwen3-0.6B or Qwen3-1.7B) that reads those features and
   **generates the transcript token by token**, like a chatbot answering. It can also output the detected language.

This explains the real size: about 0.18B encoder + 0.6B decoder, so about 0.8B parameters in total, not exactly "0.6B".
The model is built on the Qwen3-Omni foundation model, which gives it strong audio understanding, and
was trained on large amounts of Chinese/English and multilingual speech.

**Why CPU is a concern [TO VERIFY in Phase 2]:** token-by-token generation means the decoder runs once per output token,
so the time grows with transcript length. I expect decoding to dominate on CPU. I will compare encoder vs generate time.

## 2. Transformers backend vs vLLM backend
| | Transformers | vLLM |
|---|---|---|
| Role | Simple, general-purpose loading (`from_pretrained`) | High-throughput serving engine, batching |
| Speed | Slower | Described as the fastest option |
| Streaming | **Not available** | **Available** (the only official streaming path) |
| Streaming limits | n/a | No batch inference, no timestamps |
| Hardware | Can run on CPU | Official examples target CUDA GPUs **[TO VERIFY CPU/Windows support in Step 5]** |

The README says streaming is vLLM-only but does not say why. My interpretation **[TO VERIFY]**: streaming needs incremental
state handling (re-using earlier chunks and revising recent output) that the official code implements on top of vLLM's engine.
The report's streaming evaluation used **2-second chunks**, kept the **last 4 chunks unfixed** (they can still be revised),
and showed a small accuracy cost: average error rate 3.33 vs 2.69 offline (1.7B), 4.40 vs 3.48 (0.6B).

## 3. 0.6B vs 1.7B
- **1.7B:** more accurate (README, LibriSpeech clean WER 1.63 vs 2.11 for 0.6B), larger and slower.
- **0.6B:** lighter, with less memory and faster inference; the report cites TTFT as low as 92 ms and high throughput,
  but those figures are on **GPU with vLLM at high concurrency**, so they do **not** apply to my CPU setup.
- Decision: **start with 0.6B-hf** because it is the most realistic on a 6-core laptop CPU. I will measure it
  before claiming real-time performance, and optionally compare 1.7B for accuracy.

## 4. Native streaming vs application-level streaming
- **Native streaming:** the model itself keeps state between chunks and updates its output incrementally (what vLLM streaming does).
- **Application-level streaming (my approach, if native streaming is unavailable on CPU):**
  the frontend sends audio in small chunks at roughly real-time speed, the backend buffers them,
  runs the offline model on the audio accumulated so far (or a sliding window), and sends partial transcripts back;
  a final pass runs when the stream ends.
- **Chunk size vs processing window:** chunk size is how much audio is *transmitted* at a time (start at 2 s = 32,000 samples = 64 KB);
  the processing window is how much audio the model *reads* per inference. They are independent.
- Honest labelling: in the README, report and demo I will call this "chunked processing / application-level streaming",
  not native incremental inference.

## 5. Open questions to test next
- Does the `-hf` Transformers model run on CPU in float32/bfloat16, and how long does it take (load, inference, RAM)?
- Is the cost dominated by the encoder or the generate loop?
- Can vLLM run on CPU/Windows at all (Step 5), or only in Linux/WSL?
- How does accuracy change when transcribing short windows versus full audio?
