# Project walkthrough: Real-time multilingual speech-to-text on CPU

A complete, step-by-step explanation of what was built, how, why, what went wrong, and what the results mean, organised the same way as the Tetherfi assignment.
Every number is **measured** (run on my laptop) unless it is explicitly marked **estimate**.

---

## 0. The whole project in one minute

> I built a small web application that behaves like **one live phone call**. You choose a recording (a WAV file). The browser does not upload it in one piece; it cuts it into small 2-second pieces and sends them one by one, at the speed of a real conversation, over a WebSocket.
> A Python backend receives the pieces, feeds the audio to an AI speech-recognition model called **Qwen3-ASR** that runs **only on the CPU**, and sends the recognised text back while the audio is still arriving. The page shows the growing transcript and how long everything took.
> It works for English, Mandarin Chinese and Bahasa Indonesia. I measured speed, memory, CPU use, accuracy and how many calls at once the machine can handle, and used the numbers to estimate the servers needed for 50 to 1,000 calls. I also compared it with whisper.cpp (a C++ speech engine) and tested quantization.

**The honest headline results** (Intel i5-10500H laptop, 6 cores / 12 threads, 24 GB RAM, no GPU used):

| Question | Answer |
|---|---|
| Does Qwen3-ASR run on a CPU? | Yes, all three languages |
| How soon does the first text appear? | about 3 seconds after the stream starts |
| How long after the audio ends is the final text ready? | about 6.5 seconds (one stream, 11 s clip) |
| How much memory? | about 3.6 GB for the model, about 3.8 GB while streaming |
| How many calls at once? | 1 within my latency target with default settings, 2 with tuning. More still work, but get slower |
| What is the bottleneck? | CPU: one transcription already uses about 6 cores |
| How accurate? | English WER 0.35 (almost all from one product name), Mandarin CER 0.00, Indonesian WER 0.44 (fast casual speech) |

---

## 1. Everyday explanations of the key ideas (use these in the interview)

| Idea | Simple explanation |
|---|---|
| **WAV / Linear PCM** | Sound is stored as a long list of numbers. A microphone measures the air pressure many times a second and writes each measurement down. "Linear PCM" means those numbers are stored plainly, with no compression. |
| **16 kHz** | 16,000 measurements per second. 1 second = 16,000 numbers; 2 seconds = 32,000 numbers. Speech does not need more detail than that. |
| **Mono** | One microphone channel instead of two (stereo). The model expects one. |
| **16-bit** | Each measurement takes 2 bytes. So 2 seconds = 32,000 numbers x 2 bytes = **64,000 bytes (about 64 KB)**. |
| **Chunk** | A small slice of the audio sent as one message. Cutting a 60 s recording into 2 s slices gives 30 chunks. |
| **Streaming vs upload** | Upload = mailing the whole letter at the end. Streaming = reading the letter aloud to someone over the phone while they type. |
| **WebSocket vs REST** | REST is sending letters: each question needs a new envelope and the other side cannot write to you first. WebSocket is a phone call: it stays open, both sides can talk any time. That is why the server can push transcript updates the moment they exist. |
| **ASR** | Automatic Speech Recognition: audio in, text out. |
| **The model (encoder + decoder)** | Think of an **ear** and a **writer**. The audio encoder is the ear: it turns sound into a compact description of what was heard. The language-model decoder is the writer: it writes the text one token (word piece) at a time. |
| **Inference** | Using an already-trained model (not training it). |
| **CPU vs GPU** | A CPU is a few very capable workers; a GPU is thousands of simple workers doing the same sum at once. Models like this are much faster on a GPU, but the assignment says CPU only. |
| **Latency** | The waiting time. "First text latency" = how long until the first words appear. "Final latency" = how long after the last audio before the finished transcript. |
| **RTF (real-time factor)** | processing time / audio length. If 10 s of audio takes 5 s to process, RTF = 0.5 (twice as fast as real time). RTF above 1 means it cannot keep up with a live call. |
| **WER / CER** | A spelling-test score for the transcript. WER = (wrong words + missing words + extra words) / words in the correct text. 0 is perfect. Mandarin has no spaces between words, so it uses CER (per character). |
| **Concurrency** | Several calls at the same moment. Like one cashier serving a queue: each customer is fine alone, but with five in line the last one waits a long time. |
| **Quantization** | Storing the model's numbers with fewer bits, like compressing a photo: smaller file, usually a little less quality, and not always faster. |

---

## 2. What the assignment asked, and where each item is in my project

| Assignment requirement (PDF section) | Done? | Where / evidence |
|---|---|---|
| Simple web UI to select and start a WAV file (2) | Yes | `frontend/` (React); `AudioUploader.jsx` |
| Backend that receives chunks and sends them to Qwen3-ASR (2) | Yes | `backend/app/api/websocket.py`, `services/` |
| Recognised text returned to the UI *while* audio is processed (2) | Yes | `partial` messages over the WebSocket |
| Show the transcript and basic latency on the UI (2) | Yes | `Transcript.jsx`, `PerformanceMetrics.jsx` |
| English, Mandarin, Bahasa Indonesia samples (2) | Yes | `samples/` (own recordings + synthetic clips) |
| Code another engineer can understand and run (2) | Yes | `README.md`, modules with one job each |
| Handle errors: invalid audio, model failure, disconnection (2) | Yes | 12 protocol tests + 5 failure tests |
| Frontend and backend are separate logical components (2) | Yes | They only talk through the WebSocket/REST API |
| 16 kHz mono PCM WAV; stream progressively; real-call speed; explain chunk size; one stream = one call leg (3) | Yes | Header-checked in the browser, 2 s chunks paced in real time, chunk-size experiment |
| Qwen3-ASR as the main model; CPU only for the benchmark (4) | Yes | `Qwen3-ASR-0.6B-hf`, GPU hidden from PyTorch |
| Try or investigate a C++ runtime (4) | Yes, partly | whisper.cpp benchmarked; C++ builds of Qwen3-ASR itself researched, not run |
| Explain the model/runtime chosen and how it was configured (4) | Yes | README, `docs/notes/`, this document |
| Measure latency, CPU, memory, accuracy, concurrency (5) | Yes | `reports/phase6_findings.md` + CSV files |
| Load test; record CPU spec, cores, RAM, OS, runtime; find how many streams the machine handles (6) | Yes | `tests/load_test.py`, `reports/benchmark_results.csv` |
| Estimate vCPU / RAM / servers for 50-1,000 calls; mark measured vs estimated; explain assumptions (6) | Yes | `reports/capacity_estimates.md` |
| Video where I appear and speak, with a demo (6, 11) | **Not done yet (my part)** | plan in `docs/video_script.md` |
| Architecture diagram + how to improve for many calls (7) | Yes | `architecture/architecture.png`, `scaling.png` |
| Research at least one other ASR model/runtime and compare (8) | Yes | whisper.cpp measured; others researched |
| Source code, README, demo, short report, diagram (9) | All but the video | see above |

---

## 3. The architecture (and the journey of one audio chunk)

```
 Browser (React + Vite)                                    Backend (Python, FastAPI)
 +---------------------------+                             +----------------------------------------+
 | 1. pick WAV, check header |                             | websocket.py: check start message,     |
 | 2. cut into 2 s chunks    |   WebSocket  /ws/stream     |   receive frames, handle errors        |
 | 3. send each chunk when   | ==========================> | StreamSession: buffer of this call     |
 |    its audio "exists"     |  up: start, PCM frames, end | StreamTranscriber: when/what to        |
 | 4. show text + latency    | <========================== |   transcribe, partial/final messages   |
 +---------------------------+  down: ready, status,       | inference slot (1 at a time) -> thread |
                                      partial, final, error | Qwen3-ASR-0.6B on CPU (PyTorch)        |
                                                            +----------------------------------------+
```

**One chunk's journey (example: 2 seconds of English speech):**
1. The browser has the whole file in memory and has already checked that the WAV header says 16 kHz, mono, 16-bit.
2. It waits until 2 seconds of the call have "been spoken", then sends 64,000 bytes of raw samples as one binary WebSocket message.
3. The backend appends those bytes to this call's buffer (`StreamSession`) and replies `status: 2.0 s received`.
4. The transcriber notices there are at least 2 s of new audio, asks the model to transcribe the current segment (a few seconds of audio), and waits its turn in the inference slot if another call is using the model.
5. The model returns text, e.g. `"They release country."` The backend sends it as a `partial` message with timings.
6. The browser shows it in grey italics ("this may still change"). When the next chunks arrive the text is re-done with more context and improves.
7. When the browser sends `end`, the backend transcribes whatever is left, sends `final`, and the UI shows the finished text, the real-time factor, model time, CPU and RAM.

**Why the parts are separate (separation of concerns):**

| Module | Only job |
|---|---|
| `audio_service.py` | Check and load WAV/PCM audio |
| `asr_service.py` | Load Qwen3-ASR and turn audio into text. Knows nothing about WebSockets or the page |
| `stream_session.py` | The state of one call: buffer, counters, limits |
| `stream_transcriber.py` | Decides *when* to transcribe and *how much*; builds partial/final messages |
| `websocket.py` | The protocol and error handling |
| `routes.py` | REST: `/api/health`, `/api/info`, `/api/transcribe` (whole file, for testing) |
| `metrics_service.py` | Inference time, queue wait, CPU, RAM |
| `wav.js`, `streamer.js`, `websocket.js`, `useAudioStreaming.js` (frontend) | Read the WAV header, send chunks in real time, talk to the backend, keep the screen state |
| Components | `AudioUploader`, `LanguageSelector`, `Transcript`, `PerformanceMetrics`: only display and input |

Because of this, I could test the backend with no browser (a Python client) and test the frontend's logic with no browser (Node), and change either side without touching the other.

---

## 4. How the project was built, phase by phase

### Phase 1: Environment and research (can the model run on this CPU?)
**What I did:** recorded the hardware (i5-10500H, 6 cores / 12 threads, 24 GB, Windows 11; the GTX 1650 Ti is deliberately not used); installed Python 3.13 and Node 22; created a virtual environment with CPU-only PyTorch; read the Qwen3-ASR documentation; wrote notes on the model and on CPU compatibility; ran a smoke test.

**What I learned about the model:** Qwen3-ASR has an audio encoder (about 180M parameters) and a Qwen3 language-model decoder (0.6B). So the "0.6B" model is really about 0.8B in total. It supports 30 languages including all three required.

**The key finding (compatibility):**

| Option | Result |
|---|---|
| Hugging Face Transformers + `Qwen3-ASR-0.6B-hf` on CPU | Works. This is what I used. It has **no native streaming**. |
| Official `qwen-asr` package | Installs, but its examples are GPU-only, and it needs a different Transformers version than the `-hf` model |
| vLLM backend (the only official streaming mode) | Does not run natively on Windows; CPU support for Qwen3-ASR is unconfirmed |
| C++ runtimes (CrispASR, transcribe.cpp, ...) | Exist, claim CPU speed, but unverified and no Windows build I could trust |

**Smoke test result:** first load 612 s (almost all one-time download), then 6.5 s; RAM 3.58 GB; an 11.1 s clip took 5.9 s (RTF 0.53) using about 6 busy cores.

**Decision:** use Transformers on CPU and build **application-level streaming** myself (explained in section 5).

### Phase 2: Standalone ASR (before any web code)
**What I did:** wrote `audio_service.py` (validate and load WAV; reject wrong files with clear messages) and `asr_service.py` (load model once, transcribe, return text + timing + RTF), plus a test runner for the three languages.

**Samples:** my own English recording (it was stereo, so I converted it to mono with ffmpeg), plus real Mandarin and Indonesian recordings. Before I had real ones I made synthetic placeholder clips with a text-to-speech service; I kept them only as a sanity check because clean synthetic speech is too easy (0% error is not meaningful).

**Results (offline, whole file):**

| Language | Clip | Time | RTF | Error |
|---|---|---|---|---|
| English | 11 s | 5.2-6.9 s | 0.47-0.62 | WER 0.353 |
| Mandarin | 16 s | 5.4-6.2 s | 0.34-0.39 | CER 0.000 |
| Indonesian | 52 s | 45 s | 0.86 | WER 0.442 |

**Two useful discoveries:** (1) auto language detection picked the right language every time; (2) longer clips cost more *per second* (RTF 0.86 for the 52 s clip vs 0.3-0.5 for short ones). That second point decided the streaming design: re-processing an ever-growing buffer would get slower and slower, so the window must be bounded.

### Phase 3: Backend (4 small steps, each tested)
1. **Skeleton:** FastAPI app, central config (`config.py`, every setting overridable by environment variable), model loaded once at start-up. If loading fails the server stays up and `/api/health` reports the error.
2. **REST endpoints:** `/api/health`, `/api/info`, `/api/transcribe`. Tested with good files, a stereo file (converted), a non-WAV file (HTTP 400), a bad language (HTTP 400).
3. **WebSocket protocol and per-call state** (section 5.2 shows the messages). Tested with 12 cases including a frame cut in the middle of a 16-bit sample.
4. **The streaming transcription loop** (section 5.3).

**Design choice to explain:** the model call runs in a worker thread behind a **semaphore set to 1**. While one call is being transcribed the server still answers other requests and keeps other sockets open, but only one model run happens at a time, because one run already uses about 6 cores (more at once just fights for the same cores). This setting is the knob the concurrency tests vary.

### Phase 4: Frontend (React + Vite + Tailwind)
**What I built:** file picker, language and chunk-size selectors, a progress bar of audio sent, the live transcript, status, and a metrics panel; a backend-status badge; clear error messages.

**Two decisions:**
- **I parse the WAV header myself** instead of using the browser's audio decoder. The decoder silently resamples and converts the audio, which would hide the exact thing the assignment cares about (is it really 16 kHz mono PCM?). My parser also gives a helpful error: *"Unsupported audio: 2 channels instead of mono. Convert it with ffmpeg -i input.wav -ar 16000 -ac 1 -c:a pcm_s16le output.wav"*.
- **The streaming logic is plain JavaScript, not inside React.** That let me run the very same code from Node against the real backend (13 checks) without opening a browser.

### Phase 5: Integration, errors, chunk size, tuning
- **Failure tests with real servers:** server killed in the middle of a stream (client shows *connection lost*); model cannot load (health says so, streams are refused with `model_unavailable`, REST returns 503); user presses Stop (server cleans the stream up).
- **Chunk-size experiment** (0.5, 1, 2, 5 s; section 6.1).
- **Tuning experiment** (update interval and segment length; section 6.2).
- **A bug found by testing:** the setting for which model to load was ignored, so a bad model name silently loaded the default model. Fixed.

### Phase 6: Performance testing
Wrote a harness that starts its own backend and samples **its** CPU and RAM every 0.5 s while the test runs. Measured accuracy (offline vs streaming), then 1, 2, 3, 4 and 6 simultaneous streams under three configurations (section 6.3-6.5).

### Phase 7: Research and optimisation
Benchmarked whisper.cpp (4 models) and tested quantization/precision on Qwen itself (section 7), and analysed how to scale.

### Phase 8: Submission preparation
Architecture and scaling diagrams, README, tidy `requirements.txt`, technical report, capacity estimates, video plan and interview answers. While checking the README I also found and fixed a hard-coded model-cache path (`D:\hf_cache`) that would break on another machine; the cache location is now configurable through `HF_HOME` (and a `backend/.env` file).

---

## 5. Technical details

### 5.1 Audio and chunking (with the numbers)
- The browser reads the WAV header: format must be PCM, 16,000 Hz, 1 channel, 16-bit.
- Chunk size is chosen in the UI (default 2000 ms). Bytes per chunk = `16,000 samples/s x 2 bytes x seconds`. For 2 s that is 64,000 bytes.
- **Example:** the 11.1 s English clip = 177,600 samples = 355,200 bytes of audio = 5 full chunks of 64,000 bytes plus a shorter last chunk of 35,200 bytes (1.1 s). The last chunk is sent as it is.
- **Real-time pacing:** a chunk is sent only when its audio would have been spoken (the 2 s chunk at t = 2 s, the next at t = 4 s, ...). Sending everything instantly would not behave like a call and would make latency numbers meaningless.
- **Two separate ideas:** *chunk size* = how much is **sent** at once; *processing window* = how much audio the **model reads** each time (up to 10 s). They do not have to be equal.

### 5.2 The WebSocket protocol (the messages)
```
browser -> server  {"type":"start","language":"English","sample_rate":16000,"channels":1,"chunk_ms":2000}
server  -> browser {"type":"ready","stream_id":"9855cac5"}
browser -> server  [binary: 64,000 bytes of raw PCM]   (repeated, one per chunk)
server  -> browser {"type":"status","state":"receiving","audio_seconds":2.0,"chunks":1}
server  -> browser {"type":"partial","text":"They release country.","audio_seconds_transcribed":2.0,"processing_seconds":1.1,...}
browser -> server  {"type":"end"}
server  -> browser {"type":"final","text":"...","rtf":1.3,"first_transcript_latency_seconds":...,"process_rss_mb":...}
server  -> browser {"type":"error","code":"bad_sample_rate","message":"Only 16000 Hz audio is supported, got 44100."}   (on any problem, then it closes)
```
**Why the browser must send the sample rate:** raw bytes carry no header. 48 kHz audio mistaken for 16 kHz would play three times too slowly and give garbage text, with no error. So the browser reports what it read from the header and the server checks it.

**What the server guards against:** wrong sample rate or channels, unsupported language, bad JSON, audio before `start`, unknown message types, an empty stream, too many streams (`server_busy`), streams longer than 10 minutes, a missing model, a model failure mid-stream (`asr_failed`), and clients that disconnect (the stream is removed and its task cancelled).

### 5.3 How the "live" transcript is produced (application-level streaming)
**The problem:** the Transformers version of Qwen3-ASR can only transcribe a *finished* piece of audio. It cannot be fed audio bit by bit and update itself. (The official streaming mode exists only in the vLLM backend.)

**My solution, explained with an analogy:** imagine a court stenographer who can only type up a recording once it is handed over. To get live text, every few seconds you hand over *everything since the last sentence break*, get the typed text back, and show it. As more audio arrives you hand over the longer piece again and the text improves. When the piece gets long, you stop re-doing it: you freeze the text so far and start a new piece.

**Exactly what the code does** (`stream_transcriber.py`):
1. Audio accumulates in the call's buffer.
2. When at least **2 s of new audio** has arrived (and at least 1 s exists in the segment), transcribe the **current segment** and send a `partial`.
3. If the segment reaches **10 s**, cut it at the **quietest 20 ms moment in its last 3 seconds** (so we do not cut through a word), transcribe that piece one last time, **commit** its text permanently, and start a new segment from the cut.
4. While the model is busy, new audio keeps arriving and is merged into the next update, so there is never a backlog of updates.
5. On `end`, transcribe what is left and send `final`. If the last partial already covered all audio, it is reused (no extra model run).

**Example of the text improving** (successive partials from real runs of the English clip; the final line is from a later run of the same clip):
```
audio 2 s : "They release country."
audio 4 s : "The release quince trees are a family that."
audio 6 s : "The release country is a, a family that includes two powerful."
audio 8 s : "The release Quenty is a, a family that includes two powerful, all in one speech recognition model."
final     : "The release Q and three is a family that includes two powerful all-in-one speech recognition models that support language identification."
```
Early guesses are rough because the model has little context; later ones are better. This is why partial text is shown in grey italics.

**The honest cost:** because the same audio is transcribed again and again, streaming costs about **2.5 to 3 times** the compute of transcribing the clip once (English: 14 s of model time vs about 5 s for one offline pass). This is the price of faking streaming with an offline model, and it is the biggest improvement opportunity.

### 5.4 Measurements: definitions and examples
- **First text latency** = time from the start of the stream until the first words are shown. Measured both in the browser and on the server.
- **Final latency** = time from sending the last chunk until the final transcript arrives.
- **Lag** = audio the server has received minus audio covered by the newest transcript (how far "behind the speaker" the text is).
- **RTF example:** 14.3 s of model time / 11.1 s of audio = 1.29 while streaming; 5.9 s / 11.1 s = 0.53 for one offline pass.
- **WER worked example** (the English clip). Correct text (17 words, punctuation removed): *they released qwen3asr a family that includes ...*. Model output: *the release q and three is a family that includes ...*.
  Errors: they→the (1), released→release (2), qwen3asr→q (3), plus three extra words "and three is" (4, 5, 6) = **6 errors / 17 words = 0.353**. So the whole error is about one product name; the rest of the sentence is perfect.
- **CPU and RAM:** sampled every 0.5 s from the backend's whole process tree with `psutil` (100% = one core).
- **Normalisation:** lowercase, punctuation removed; Mandarin CER ignores spaces. Same rule everywhere.

---

## 6. Results

### 6.1 Chunk size (how audio is *sent*; 2 repetitions per cell)
| Chunk | First text | Final latency after end | Model time (English / Mandarin) | Error rate |
|---|---|---|---|---|
| 0.5 s | 3.0-3.2 s | 6.4 / 4.0 s | 14.4 / 16.5 s | same |
| 1 s | 3.2 s | 5.9 / 4.4 s | 14.3 / 16.9 s | same |
| **2 s** | 3.0 s | 5.9 / 3.7 s | 13.9 / 15.9 s | same |
| 5 s | 6.9-7.4 s | 4.0 / 3.5 s | 7.4 / 8.9 s | same |

**Why I chose 2 s:** between 0.5 s and 2 s almost nothing changes, because the server updates every 2 s of audio whatever the chunk size. 5 s delays the first text by about 4 s (nothing can be transcribed before the first chunk exists) but halves the model work. 2 s gives early text with little overhead. The point for the interview: *chunk size controls how soon text can start; the update interval controls how much compute is spent.*

### 6.2 Processing settings (update interval / segment length)
| Update / segment | English: first text, model time, WER | Indonesian 52 s: mean/max lag, model time |
|---|---|---|
| **2 s / 10 s (kept as default)** | 2.9 s, 14.0 s, 0.353 | 5.5 / 12.7 s, 56.9 s |
| 4 s / 10 s | 6.0 s, 10.6 s, 0.353 | 5.8 / 10.5 s, 54.4 s |
| 3 s / 6 s | 6.0 s, 8.3 s, **0.471** | 6.7 / 14.2 s, 49.2 s |
| 4 s / 6 s | 5.9 s, 8.2 s, **0.471** | 6.5 / 14.2 s, 47.9 s |

**What this shows:** no setting removes the lag on fast speech (the 52 s Indonesian clip needs about 0.9 s of compute per second of audio even in the cheapest setting, so the speech density itself is the cost). Shorter segments save compute but **hurt accuracy** (cutting more often splits phrases and removes context). A longer update interval saves about 25% compute for the same accuracy but doubles the wait for the first text. I kept 2 s / 10 s because first-text latency is a measured criterion of the assignment.

### 6.3 Accuracy (reference texts typed by the speaker)
| Clip | Metric | Offline | Streaming (2 runs) |
|---|---|---|---|
| English, 11 s | WER | 0.353 | 0.353, 0.353 |
| Mandarin, 16 s | CER | 0.000 | 0.000, 0.000 |
| Indonesian, 52 s casual conversation | WER | 0.442 | 0.363, 0.469 |

Notes: streaming gives the same accuracy as offline for English and Mandarin; Indonesian varies by about 0.1 between runs because cut points depend on timing. Some Indonesian "errors" are informal spellings that WER counts as wrong ("enggak" vs "nggak"), mixed with true mistakes ("mengedit" heard as "menggaduh"). Only three short clips from one speaker: this proves the pipeline works, not general accuracy.

### 6.4 CPU and memory
| Situation | CPU (100% = 1 core) | RAM |
|---|---|---|
| Loading the model (6 s, cached) | average about 200%, peak about 1000% | rises to 3.6 GB |
| Idle | about 0% | 3.6 GB |
| 1 stream | about 430% average, peak about 610% | 3.8 GB |
| 6 streams | about 540% average | 3.9-4.0 GB |

One model copy dominates memory. The first stream adds about 200 MB (working memory); each further stream only about 15 MB. **CPU, not memory, is the limit.**

### 6.5 Concurrency (N simultaneous real-time streams)
"Acceptable" = nothing failed, worst final latency <= 10 s, average lag <= 5 s. (These thresholds are my own assumption.)

| Streams | Worst final latency | Total queue wait | CPU (avg) | RAM | Acceptable? |
|---:|---:|---:|---:|---:|---|
| 1 | 6.5 s | 0 s | 428% | 3.8 GB | yes |
| 2 | 11.7 s (7.7-7.8 s with 4 s updates, or with 2 inferences x 3 threads) | 18 s | 499% | 3.8 GB | only in the tuned settings |
| 3 | 18.6 s | 45 s | 523% | 3.8 GB | no |
| 4 | 20.2 s | 80 s | 527% | 3.9 GB | no |
| 6 | 35.7 s | 192 s | 547% | 3.9 GB | no |

**Plain-language reading (the cashier):** one cashier (the model) is fully busy with one customer. With two customers the second waits; with six, the last waits more than half a minute. Nobody was turned away (no failures); the service just got slower. Accuracy did not change under load. **Measured capacity of this laptop: 1 call (default) or 2 calls (tuned).**

### 6.6 From measurements to server estimates (estimates, not measurements)
Method (example for 50 calls): if one 12-vCPU worker serves 2 calls, 50 calls need 50 / 2 = 25 workers; add 30% headroom: 25 x 1.3 = 32.5, rounded up to **33 workers**; 33 x 12 = **396 vCPU**; 4 workers fit on a 48 vCPU / 32 GB server, so **9 servers**; model RAM about 4 GB each = **132 GB**.

| Calls | Workers | vCPU | RAM | Servers (48 vCPU / 32 GB) |
|---:|---:|---:|---:|---:|
| 50 | 33 | 396 | 132 GB | 9 |
| 100 | 65 | 780 | 260 GB | 17 |
| 200 | 130 | 1,560 | 520 GB | 33 |
| 500 | 325 | 3,900 | 1,300 GB | 82 |
| 1,000 | 650 | 7,800 | 2,600 GB | 163 |

I also showed a hypothetical "after optimisation" scenario (5 calls per worker: 13 workers for 50 calls, 260 for 1,000). That number is a guess from one measurement (the 2.5-3x repeated-compute cost). It was **not built or tested** and is labelled that way. Assumptions that may make reality worse: linear scaling, calls all speaking at once, my latency thresholds, a lighter clip mix than real chatty calls.

---

## 7. Research: alternatives and quantization

### 7.1 whisper.cpp (a C++ engine) vs Qwen3-ASR, same clips, same machine, CPU only
Whisper time includes starting the program (about 0.3-1 s); Qwen time is inference only with the model already loaded.

| Model | English 11 s | Mandarin 16 s | Indonesian 52 s | RAM |
|---|---|---|---|---|
| **Qwen3-ASR-0.6B** (Transformers, float32) | 4.8-5.9 s, WER 0.353 | 4.9-6.9 s, CER 0.000 | 44-45 s, WER 0.442 | 3.6-3.8 GB |
| whisper small | 5.6 s, 0.235 | 5.6 s, 0.000 | 15.4 s, 0.522 | 0.8-0.9 GB |
| whisper small 5-bit | 6.1 s, 0.176 | 6.1 s, 0.000 | 18.7 s, 0.522 | 0.5-0.6 GB |
| whisper base 5-bit | 2.0 s, 0.235 | 2.3 s, 0.000 | 13.6 s, 0.699 | 0.2-0.3 GB |
| whisper large-v3-turbo 5-bit | 23 s, 0.118 | 24 s, 0.000 | 45.7 s, failed | 0.85 GB |

**Answers to the assignment's questions ("why might the alternative be better or worse?"):**
- *Less CPU or memory?* Memory: yes, whisper small uses about a quarter. CPU: it still used about 6 cores, but for less time on the dense clip.
- *Easier to run in real time?* Faster on the dense Indonesian clip (about 3x), similar on short ones.
- *Multilingual?* Both cover the three languages. Whisper small was better on English, Qwen better on Indonesian, Mandarin tied.
- *Caveat:* whisper.cpp is a different model and is also an offline decoder, so it would need the same chunking. The large-v3-turbo model produced only 10 of 121 words on the long Indonesian clip (on both runs, with default settings), so that row is a failure to finish the clip, not a word-accuracy result. I did not investigate the cause.
- *What I would test next:* a C++ build of **Qwen3-ASR itself** (CrispASR / transcribe.cpp), vLLM streaming under WSL2, faster-whisper int8, a voice-activity detector to skip silence, and more speakers and noisy phone audio.

### 7.2 Quantization and precision on Qwen3-ASR (measured)
| Variant | English | Mandarin | Indonesian | Verdict |
|---|---|---|---|---|
| float32 (baseline) | 4.8 s | 4.9 s | 44 s | best |
| bfloat16 | 29.6 s | 40 s | 145 s | about 6x slower (this CPU has no native bf16) |
| int8 dynamic | 4.0 s | 4.5 s | 103 s, WER 0.575 | 15% faster on short clips, but slower and less accurate on the long one |
| whisper 5-bit (vs full precision) | similar | similar | similar | about 60% smaller, same accuracy, **not faster** |

**Lesson:** "smaller number format" does not automatically mean "faster". Speed depends on whether the CPU has fast hardware for that format. Here, quantization saved memory and disk, not time.

---

## 8. Problems faced and how I solved them

| # | Problem | How I found it | Cause | Fix | What it taught me |
|---|---|---|---|---|---|
| 1 | Official streaming does not work for me | Reading the docs, then CPU/Windows research | Streaming exists only in the vLLM backend (no native Windows, CPU unconfirmed) | Built application-level streaming and measured its cost | Understand what a library actually supports before designing around it; be honest in how you describe it |
| 2 | "0.6B" model uses 3.6 GB | Smoke test | The model has a separate 180M encoder plus the 0.6B decoder, in float32 | Documented real size; planned memory around 4 GB per model copy | Check real numbers, not names |
| 3 | My own English recording was stereo | Format check showed 2 channels | Recorder default | Converted with ffmpeg; the backend and UI now explain how to convert | Validate input early with a helpful message |
| 4 | First test crashed: "soxr not found" | Traceback | Transformers needs `soxr` to load audio | Installed it and added it to the requirements | Read the error text; it named the fix |
| 5 | Background job output was garbled and showed no download progress | Log unreadable | PowerShell redirect writes UTF-16 and hides progress bars | Ran the long job in the visible terminal | Use the right tool for long interactive jobs |
| 6 | 52 s clip could be cut off | Planned for long clips | Token limit of 256 | Raised to 512 | Think about the longest input |
| 7 | Streaming looked slower than offline | RTF 1.4 vs 0.5 | The same audio is re-transcribed each update | Measured it, bounded the window (10 s segments), tuned settings, reported honestly | The cost of faking streaming is real and measurable |
| 8 | First-text latency looked about 2 s too good | Reviewing the test client | It sent the first 2 s chunk at t = 0, before that audio "existed" | Each chunk is now sent when its audio would have been spoken | Wrong measurement method = wrong conclusions |
| 9 | Load test reported 0% CPU and 4 MB RAM | Numbers were impossible | On Windows the venv's `python.exe` is a launcher; the real server is a child process, and I was measuring the launcher | Measure the whole process tree, re-ran the entire load test | Sanity-check measurements; I caught it before reporting |
| 10 | "Idle" CPU looked busy | Idle reading of 78% | I measured right after model load, while it was still settling | Added a settle period | Measurement windows matter |
| 11 | Bad model name still loaded the default model | A failure test did not fail | The `ASR_MODEL_ID` setting was never passed to the service | Passed it through; the test now passes | Tests that try to break things find real bugs |
| 12 | A protocol test failed | Test output | My test compared 0.15625 s with a value rounded to 0.16 s | Fixed the test tolerance (the server was right) | Distinguish test bugs from product bugs |
| 13 | Model would not load on another machine | Reviewing the README | Cache path hard-coded to `D:\hf_cache` | Removed it; `HF_HOME` / `backend/.env` now configure it | Never hard-code personal paths |
| 14 | Whisper large-v3-turbo failed on the long clip | 10 of 121 words | Unknown (default settings, repeated first phrase) | Reported as a failure, did not claim accuracy from it | Say "I don't know why" rather than guess |
| 15 | bfloat16 / int8 did not help | Quantization experiment | No native bf16 on this CPU; int8 kernels slower on the long decode | Kept float32 and documented the evidence | Measure before optimising |

---

## 9. Key decisions and the reasons

| Decision | Why | Alternative considered |
|---|---|---|
| Qwen3-ASR-0.6B-hf with Transformers on CPU | Required model; smallest; the only route I could verify on CPU-only Windows | 1.7B (heavier, not benchmarked), vLLM (not available here) |
| Application-level streaming (re-transcribe the current segment) | Native streaming is unavailable; this still delivers text while audio arrives | Wait for the whole file (not allowed: must stream) |
| WebSocket | Persistent two-way channel, server can push partial text, detects disconnects | REST per chunk (needs a request each time, cannot push) |
| FastAPI + Python | Model ecosystem is Python; REST and WebSocket in one app | Node backend (would need to call Python for the model anyway) |
| React + Vite + Tailwind | Quick, familiar, the assignment suggests React | Plain HTML |
| 2 s chunks (64 KB) | Early first text with little overhead; the experiment showed no difference from 0.5 to 2 s | 0.5 s (more messages, no gain), 5 s (slower first text) |
| 2 s updates, 10 s segments, cut at quiet points | Bounded cost per update, best first-text latency and English accuracy of the settings tried | 6 s segments (cheaper but worse accuracy), 4 s updates (cheaper, slower first text) |
| One inference at a time (semaphore = 1) | One inference already uses about 6 cores; parallel runs contend | 2 x 3 threads (helps 2 streams, no gain beyond) |
| Parse WAV header in the browser | Verify the real format instead of silently converting | `decodeAudioData` (resamples silently) |
| Streaming logic as plain JS, tested in Node | Testable without a browser; same code as the app | Logic inside React components |
| Real recordings + reference transcripts for accuracy | Honest numbers; synthetic speech is too easy | Only TTS clips |
| WER for English/Indonesian, CER for Mandarin | Mandarin has no word spaces | WER for all |
| Same text normalisation everywhere | Fair, repeatable comparison | Ad-hoc per test |
| Test with a fake model for the logic, real servers for failures | Fast deterministic logic tests plus realistic failure tests | Only manual testing |
| Report measured and estimated numbers separately | The assignment says to; protects credibility | Single table of "capacity" |
| Keep float32 | Quantization gave no benefit on this CPU | int8 / bfloat16 |
| Compare with whisper.cpp | A C++ CPU runtime, same samples, same machine | Only reading about it |

---

## 10. Limitations (say these before you are asked)
- It is application-level streaming, not native: partial text can change, and on dense speech the transcript lags behind (up to about 14 s on the 52 s Indonesian clip).
- Low concurrency on a laptop CPU; all server numbers for 50-1,000 calls are **estimates** and probably optimistic (they assume linear scaling).
- Small test set: three short clips from one speaker (plus clean synthetic clips). Most timings are single runs; the laptop's thermal behaviour and background load were not controlled.
- The load test used English and Mandarin clips only; calls started within 2 s of each other; the "acceptable latency" thresholds are mine.
- Windows only; no authentication or TLS; WAV files only (no microphone).
- Only whisper.cpp was measured as a C++ runtime. C++ builds of Qwen3-ASR, vLLM streaming, faster-whisper and sherpa-onnx were researched, not run.
- The React page itself should be checked by eye in a browser; my automated checks covered its logic, not its appearance.

---

## 11. How to explain it (interview and video)

**60-second pitch:** *"I built a web app that streams a WAV file in 2-second chunks at call speed over a WebSocket to a FastAPI backend that runs Qwen3-ASR on the CPU and sends partial and final transcripts back to a React page with latency figures. Qwen's streaming mode is not available on a Windows CPU, so I implemented application-level streaming: buffer the audio, transcribe the current segment every 2 seconds, commit segments at quiet points, finish with a final pass. I measured about 3 s to first text, 3.8 GB of memory and about 6 cores per stream, so one laptop handles 1-2 calls; CPU inference is the bottleneck. I compared whisper.cpp and quantization, and estimated servers for 50 to 1,000 calls, clearly marked as estimates."*

**Three sentences that show maturity:**
1. "This is chunked processing, not native streaming, and it costs about 2.5-3x the compute of a single pass."
2. "These capacity numbers for 1,000 calls are estimates from a laptop, and I list the assumptions that could make them wrong."
3. "My first load test measured the wrong process; I noticed the numbers were impossible, fixed it and re-ran everything."

**If asked "what would you do with another week?"** Test Qwen3-ASR in a C++ runtime with streaming, add voice-activity detection to skip silence, try true incremental decoding, evaluate more speakers and noisy phone audio, and put gateways and a worker pool behind a queue (see `architecture/scaling.png`).

**Demo order (about 2 minutes):** English (watch the grey text improve, point out the "Q and three" name error), Mandarin with auto-detect, Indonesian (the lag is a good teaching moment), then upload a stereo file to show the clear error message.

---

## 12. Where things are

```
README.md                         install, run, tests, limitations
architecture/architecture.png     current design;  scaling.png = proposed design
reports/technical_report.md       the short report for submission
reports/capacity_estimates.md     measured vs estimated sizing with assumptions
reports/phase1..7_findings.md     the detailed record of each phase
reports/*.csv                     raw data (accuracy, benchmark, chunk size, tuning, whisper, quantization)
backend/app/                      main.py, api/, core/config.py, services/
frontend/src/                     App.jsx, components/, hooks/, services/
tests/                            tests, experiments, load-test harness
samples/                          test audio and reference transcripts
docs/notes/                       my research notes (model, CPU compatibility)
docs/video_script.md              video plan and interview answers
```

**Test counts:** 12 WebSocket protocol cases, 7 fake-model logic tests, 13 frontend-logic checks against the live backend, 5 real-server failure scenarios (all passing).
