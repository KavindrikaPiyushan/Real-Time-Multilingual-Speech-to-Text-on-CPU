# Video presentation plan and interview prep

Rules from the assignment: you must appear and speak, in your own words; show a working demo of English, Mandarin and Bahasa Indonesia; explain what you built, how, results, challenges, what you learned and what you would improve. Target 8-12 minutes.
These are talking points, not a script to read. Use your own wording; you will be asked about anything you say.

## Before recording
- [ ] Backend and frontend running; badge in the UI shows "Backend ready".
- [ ] Close other heavy programs (the model uses about 6 cores; background load makes latency look worse).
- [ ] Have these open: the UI, `architecture/architecture.png`, `reports/technical_report.md`, VS Code with `stream_transcriber.py` and `useAudioStreaming.js`.
- [ ] Do one dry run of all three languages so you know the timing (each clip takes about the length of the audio plus a few seconds).
- [ ] Camera on for the intro and the wrap-up so you "personally appear".

## Timeline (about 10-11 minutes)
| Time | Section | Talking points |
|---|---|---|
| 0:00-1:00 | Introduction | Who you are, what you studied/built before, and one sentence: "I built a web app that streams a WAV file like a live call to Qwen3-ASR running only on CPU, and measured how it behaves." |
| 1:00-2:00 | Problem and objective | One call leg = one stream; chunked streaming not one big upload; CPU only; three languages; measure latency, CPU, memory, accuracy, concurrency; estimate servers for 50-1000 calls. |
| 2:00-4:00 | Architecture and technologies | Show `architecture.png`. React UI -> WebSocket -> FastAPI -> Qwen3-ASR. Why React/FastAPI/WebSocket (persistent two-way connection, binary audio up, JSON text down). Separate frontend/backend. One line per module: websocket.py, stream_session, stream_transcriber, asr_service, audio_service, metrics_service. |
| 4:00-6:00 | Live demo (3 languages) | See demo steps below. Narrate what happens behind the scenes while it runs. |
| 6:00-8:00 | AI model and streaming explained | What ASR is (audio encoder + language-model decoder). Why 0.6B. Qwen's Transformers backend is offline only; official streaming needs vLLM (no Windows, CPU unconfirmed) so I did application-level streaming. Chunk size (2 s, how data is sent) vs processing window (what the model reads, up to 10 s). Partial text can change; segments are committed at quiet points; final pass at the end. |
| 8:00-10:00 | Results | Latency, CPU/RAM, accuracy, concurrency, alternatives (numbers below). Be clear which are measured and which are estimates. |
| 10:00-11:00 | Challenges, learning, next steps | See below. End on camera. |

## Live demo steps
1. Show the UI and the green backend badge. Mention the model is already loaded (about 6 s start-up, about 3.6 GB RAM).
2. **English:** choose `samples/english.wav`, language English, chunk 2 s, Start. While it streams, point to: progress bar (audio sent at real-time speed), grey text that may still change, the updates table (each row = one model pass), first-text latency (about 3 s). When done, show final latency, RTF, model time, CPU, RAM.
   Point out honestly the "Q and three" error and why (a product name the model has not seen as one word).
3. **Mandarin:** `samples/mandarin.wav`, Auto-detect. Show that the language was detected and the text is correct.
4. **Bahasa Indonesia:** `samples/indonesian.wav` is 52 s. Either run it fully (the lag is visible and a good teaching moment) or run `indonesian_tts.wav` for a shorter demo, and say which one it is.
5. Error handling (30 seconds): upload a stereo or 44.1 kHz file and show the message that tells you how to convert it; or stop the backend mid-stream and show the connection-lost message.
6. Optional: show the chunk-size dropdown and explain that 5 s chunks delay the first text.

## Key numbers (all measured on i5-10500H, 6C/12T, 24 GB, CPU only)
- Model load about 6 s (cached); RAM about 3.6 GB idle, 3.8 GB with a stream, +about 15 MB per extra stream.
- One stream: first text about 3 s, final about 6.5 s after the audio ends, lag mean 1.3 s (English clip). One stream uses about 6 cores.
- Accuracy: English WER 0.353 (almost all from the name "Qwen3-ASR"), Mandarin CER 0.000, Indonesian WER 0.442 (casual speech, 52 s). Streaming equals offline for English/Mandarin.
- Chunk size: 0.5-2 s about the same; 5 s delays first text about 4 s but halves model work.
- Concurrency: 1 stream OK with defaults, 2 OK with tuning (4 s updates or 2 inferences x 3 threads), 3-6 slower (final latency 15-44 s) but no failures. Bottleneck = CPU inference; queue wait rose from 0 to about 190 s total at 6 streams.
- Alternatives: whisper small about 3x faster on the dense Indonesian clip and 1/4 of the RAM, better English, worse Indonesian. bfloat16 6x slower. int8 no clear win. 5-bit quantization shrinks size, not time.
- Estimates (not measured): about 33 / 65 / 130 / 325 / 650 workers (12 vCPU each) for 50 / 100 / 200 / 500 / 1000 calls, based on 2 calls per worker plus 30% headroom.

## Challenges and what to say about them
- Qwen's native streaming is not available on Windows/CPU, so I built and explained application-level streaming and measured its cost (about 2.5-3x the compute of one pass).
- First load test showed 0% CPU and 4 MB RAM: the sampler was watching the venv launcher process instead of the real server (a child process). Fixed by measuring the process tree, then re-ran everything.
- A test caught that the model-ID setting was ignored (the config value was never passed to the service).
- My first client sent the first chunk at t=0, which made first-text latency look 2 s too good; fixed so each chunk is sent when its audio exists.
- Honest limits: three short clips, one speaker; single runs; estimates assume linear scaling.

## What I would do next
Test Qwen3-ASR in a C++ runtime (CrispASR / transcribe.cpp) and vLLM streaming under WSL2; add voice-activity detection to skip silence; real streaming instead of re-transcribing; per-language model choice; more speakers and noisy phone audio; a worker pool behind a queue as in `scaling.png`.

## Likely interview questions: short answers grounded in this project
**Architecture**
- *Why separate frontend/backend?* Independent change and scaling; the contract is the WebSocket protocol, which I tested without a browser.
- *Why WebSocket not REST?* One persistent two-way connection: audio frames up, partial/final text and status down, disconnect detection. REST would need a request per chunk and could not push updates.
- *Responsibility of each service?* asr_service loads the model and transcribes; audio_service validates/loads WAV and PCM; stream_session holds one call's buffer and limits; stream_transcriber decides when and what to transcribe; websocket.py handles the protocol and errors; metrics_service measures.
**Audio**
- *Linear PCM / 16 kHz / mono?* Uncompressed samples; 16,000 samples per second; one channel (the model expects it, speech needs no stereo).
- *Chunking and last chunk?* 2 s = 32,000 samples = 64,000 bytes; the last chunk is just shorter and is sent as is; the server keeps a leftover odd byte so a sample is never split.
- *Why 2 s?* Small enough for early text, large enough to avoid overhead; measured 0.5-5 s: little difference up to 2 s, 5 s delays the first text.
- *Disconnect mid-stream?* The server removes the stream and cancels its task (a model call already running finishes and is dropped); the client shows "connection lost". Tested.
**AI/ML**
- *What is ASR / inference / quantization?* Audio to text; running a trained model; storing weights in fewer bits (smaller, sometimes faster). I tested bfloat16 and int8: no gain on this CPU.
- *How does Qwen3-ASR work?* Audio encoder turns the waveform into features; a language-model decoder writes the text token by token.
- *Why 0.6B?* Smaller and more realistic for CPU; 1.7B is more accurate but heavier (not benchmarked here).
- *CPU vs GPU?* GPUs run many operations in parallel and would be much faster; the assignment is CPU-only, so one inference occupies about 6 cores.
- *Runtime limits?* Offline-only Transformers backend (no native streaming), float32 only on this CPU, about 3.6 GB per model copy.
**Performance**
- *Latency / RTF?* First text and final text delays; RTF = processing time / audio length (below 1 = faster than real time). Streaming RTF was above 1 because the same window is re-transcribed; offline it was about 0.5.
- *How were CPU and RAM measured?* psutil sampling every 0.5 s of the server process tree (child processes included).
- *WER/CER?* WER = (substitutions + deletions + insertions) / reference words; CER for Mandarin because it has no spaces between words.
- *Bottleneck and 1,000 calls?* CPU inference. Add workers behind a queue and load balancer, reduce work per call (streaming, silence skipping), autoscale on queue wait; the sizing table is an estimate.
**Problem solving**
- *Hardest part?* Making streaming work around an offline model and then proving the latency cost with measurements (and catching my own measurement bugs).
- *If the model fails?* The server reports `asr_failed` or `model_unavailable`, the UI shows the message, and health shows the error. Tested.
- *How to deploy?* Containerise the backend, one model process per set of cores, put gateways and a queue in front (diagram), add TLS and authentication, monitor queue wait, CPU and latency.
