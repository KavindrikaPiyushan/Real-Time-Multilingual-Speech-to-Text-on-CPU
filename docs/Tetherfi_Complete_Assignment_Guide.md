# Tetherfi Fresher Engineering Technical Assignment
## Complete Learning, Development, Testing, and Submission Guide

**Assignment:** Real-Time Multilingual Speech-to-Text on CPU  
**Focus:** AI/ML + Full-Stack Engineering  
**Primary constraint:** CPU-only inference (no GPU)  
**Required languages:** English, Mandarin Chinese, and Bahasa Indonesia

---

## Purpose of this guide

This guide turns the five-page Tetherfi assignment into a practical learning and development roadmap. The assignment is not simply about building a speech-to-text interface. It asks you to build a working end-to-end system, understand its components, measure its performance, reason about scaling, and explain your technical decisions.

By completing the work, you should be able to:

1. Explain the complete system architecture.
2. Explain how audio is read, divided into chunks, and streamed.
3. Explain how Qwen3-ASR converts audio into text.
4. Explain how the backend communicates with the AI model.
5. Explain how the frontend receives and displays recognized text.
6. Measure latency, CPU usage, memory, and transcription accuracy.
7. Perform concurrency testing and estimate server requirements.
8. Explain the code, technologies, challenges, and design decisions during your presentation or interview.

**Important approach:** Treat this as a learning and engineering project. Build it incrementally, record what you actually test, and make sure you can explain the code you submit.

---

# 1. Understand exactly what you need to build

The application should behave like one live voice-call leg. Imagine a person speaking English, Mandarin Chinese, or Bahasa Indonesia during a telephone call.

Instead of waiting for the entire recording to finish, the application should:

1. Read a WAV audio file.
2. Divide the audio into smaller chunks.
3. Send the chunks progressively to the backend.
4. Process the audio using Qwen3-ASR.
5. Return recognized text to the frontend.
6. Display transcript updates as processing progresses.
7. Show performance information, including latency.

### Expected application workflow

```text
WAV Audio File
16 kHz · Mono · Linear PCM
        |
        v
Frontend – React / Next.js
Read audio and divide it into chunks
        |
        | WebSocket connection
        v
Backend – Python / FastAPI
Receive chunks and manage audio streams
        |
        v
Qwen3-ASR Model
CPU-based speech recognition
        |
        v
Recognized text
        |
        v
Frontend Transcript Display
Live-style transcript + latency information
```

This is the basic architecture proposed for the implementation.

> **Important streaming distinction:** Sending chunks progressively does not automatically mean the model generates a new transcript for every chunk. The application must decide how chunks are buffered and passed to the ASR model. Audio transport chunk size and the model's ASR processing window are separate concepts.

---

# 2. Recommended technologies

Keep the frontend and backend as separate logical components that communicate through an API or streaming interface.

| Component | Recommended technology | Purpose |
|---|---|---|
| Frontend | React.js + Vite | User interface |
| Styling | Tailwind CSS | UI styling |
| Backend | Python + FastAPI | API and application logic |
| Streaming | WebSocket | Progressive, two-way audio and result communication |
| AI model | Qwen3-ASR | Speech recognition |
| Audio processing | SoundFile / NumPy | WAV reading and audio processing |
| Performance monitoring | psutil | CPU and RAM measurements |
| Testing | Python scripts / pytest | Functional and load testing |

### Why these technologies?

- **React:** Lets you apply existing frontend development knowledge to build the user interface.
- **Python:** The Qwen3-ASR ecosystem is Python-oriented, making model integration practical.
- **FastAPI:** Supports REST APIs and WebSockets, allowing both communication styles in one backend.
- **WebSocket:** Provides a persistent, two-way connection for sending audio chunks and receiving transcript updates or status messages.
- **psutil:** Helps observe CPU utilization and memory consumption.

### C++ inference investigation

The assignment says that a C++-based inference option or runtime is preferred, but not mandatory. Investigate this after establishing a working CPU-based Qwen3-ASR implementation. If the selected Qwen setup does not have a practical supported C++ route, document what you investigated and explain the alternative you used.

---

# 3. The main technical challenge: Qwen3-ASR on CPU

Before building the complete application, investigate how Qwen3-ASR can run on the available CPU machine.

The guide identifies two Qwen3-ASR inference backend options:

1. **Transformers backend:** Uses the Hugging Face Transformers ecosystem.
2. **vLLM backend:** An optimized inference engine. The guide notes that the official Qwen3-ASR streaming implementation uses its vLLM backend and does not expose the same streaming interface through the Transformers backend.

This creates an important compatibility question because the assignment requires the main test to run on CPU. Do not assume that a GPU-oriented vLLM streaming example will work on your CPU machine. Verify the current support and requirements for the exact model and runtime versions you choose.

### Recommended investigation order

| Option | Approach | Purpose |
|---|---|---|
| A | Qwen3-ASR with Transformers on CPU | Establish the required CPU inference baseline |
| B | Qwen3-ASR streaming with vLLM | Investigate whether a supported CPU configuration is practical |
| C | Alternative C++ ASR runtime | Compare CPU performance and multilingual support |

### Practical fallback: application-level streaming simulation

If native streaming inference is not practical on the CPU configuration, the application can still transmit audio progressively and process accumulated audio windows:

1. The frontend sends audio progressively.
2. The backend buffers incoming chunks.
3. The backend processes available audio using Qwen3-ASR.
4. The backend sends transcript updates to the frontend.
5. The backend performs final transcription when the stream ends.

Clearly describe this as **application-level streaming or chunked processing**, not native incremental streaming inference, unless the model actually supports incremental streaming in the chosen runtime.

This is an important engineering distinction to explain during the interview.

---

# 4. Understand audio streaming before coding

## 4.1 What is Linear PCM WAV?

WAV is an audio container format. Linear PCM describes how the audio samples are represented.

The assignment's preferred input format is:

| Property | Preferred value |
|---|---|
| Sample rate | 16,000 Hz (16 kHz) |
| Channels | 1 (mono) |
| Encoding | Linear PCM |
| Sample format | Typically 16-bit PCM |

### What does 16 kHz mean?

A sample rate of 16 kHz means the audio contains 16,000 samples per second.

- 1 second = 16,000 samples.
- 2 seconds = 32,000 samples.
- 5 seconds = 80,000 samples.

## 4.2 What is chunking?

Imagine a 60-second recording. Instead of uploading all 60 seconds at once, divide it into smaller pieces and send them progressively.

Example using six 10-second chunks:

```text
60-second recording
  |-- Chunk 1: 0–10 sec
  |-- Chunk 2: 10–20 sec
  |-- Chunk 3: 20–30 sec
  |-- Chunk 4: 30–40 sec
  |-- Chunk 5: 40–50 sec
  `-- Chunk 6: 50–60 sec

Chunks are sent progressively
        |
        v
Backend receives and tracks audio chunks
        |
        v
ASR processing
        |
        v
Transcript updates
```

Each audio stream should be treated as one call leg. The backend should maintain the state of each stream independently.

## 4.3 Choosing a chunk size

Start with **2-second chunks** for the first implementation, then test other chunk sizes.

At 16 kHz:

```text
Samples per chunk = 16,000 samples/second × 2 seconds
                  = 32,000 samples
```

For 16-bit PCM (2 bytes per sample):

```text
Bytes per chunk = 32,000 samples × 2 bytes
                = 64,000 bytes
                ≈ 64 KB
```

### Why start with 2 seconds?

- Smaller chunks can reduce the time before processing begins.
- Larger chunks provide more speech context.
- Very small chunks may create excessive processing and communication overhead.
- The system needs a balance between responsiveness and recognition quality.

Do not assume that 2 seconds is optimal. Test different chunk sizes and compare the observed results.

### Two concepts to explain in the interview

- **Audio chunk size:** How much audio is transmitted at a time.
- **ASR processing window:** How much audio the model uses to generate a transcript.

These values do not have to be the same.

---

# 5. Understand WebSocket communication

## Why not use only a normal REST API?

A typical REST request-response interaction looks like this:

```text
Frontend -- request --> Backend
Frontend <-- response -- Backend
```

A WebSocket connection stays open and allows both sides to send messages:

```text
Frontend <==== persistent WebSocket connection ====> Backend

Audio chunks  -------------------------------> 
Transcript updates <---------------------------
Status / errors <-----------------------------
```

For this assignment, WebSocket is suitable because:

- A new connection is not required for every audio chunk.
- The backend can send transcript updates whenever they become available.
- The backend can send processing status and error messages.
- The application can detect disconnected streams.

FastAPI supports receiving binary WebSocket messages, including through `receive_bytes()`.

### Concepts to understand before implementation

- HTTP vs. WebSocket
- Client and server
- Persistent connections
- Binary messages
- WebSocket connection lifecycle
- Handling disconnections

---

# 6. Learn how Qwen3-ASR works

**ASR** means **Automatic Speech Recognition**. Its purpose is to convert spoken language into written text.

Example:

```text
Input audio:
A person says, "Good morning, how are you?"

        |
        v

Qwen3-ASR:
The model analyzes the audio and predicts the spoken words.

        |
        v

Output text:
Good morning, how are you?
```

## 6.1 High-level model components

The guide describes two important components:

1. **Audio encoder:** Extracts useful information from the audio.
2. **Language model decoder:** Generates the recognized text.

The model also supports automatic language detection.

## 6.2 Required languages

The application must demonstrate speech recognition for:

- English
- Mandarin Chinese
- Bahasa Indonesia

## 6.3 Model sizes to investigate

| Model | Parameters | Consideration |
|---|---:|---|
| Qwen3-ASR-0.6B | 0.6 billion | A smaller candidate to investigate for CPU deployment |
| Qwen3-ASR-1.7B | 1.7 billion | A larger model to compare for recognition quality and resource requirements |

### Recommended starting point

Start by investigating `Qwen/Qwen3-ASR-0.6B-hf`.

Reasons:

- It is smaller than the 1.7B variant.
- It supports the three required languages.
- It provides a practical starting point for CPU experiments.

Measure actual performance before deciding whether it is suitable for the application. Do not claim that it meets real-time requirements until your measurements support that conclusion.

## 6.4 Important AI/ML terms

| Term | Meaning |
|---|---|
| ASR | Automatic Speech Recognition |
| Model | A trained machine learning system |
| Parameters | Learned numerical values inside a model |
| Inference | Using a trained model to make predictions |
| CPU inference | Running model calculations using the CPU |
| GPU inference | Running model calculations using a GPU |
| Quantization | Representing model weights with lower numerical precision to reduce resource requirements |
| Tokenization | Converting text into tokens for model processing |
| Multilingual ASR | Recognizing speech in multiple languages |

You do not need to train a model for this assignment. You need to integrate a pretrained model and understand its inference process.

---

# 7. Proposed project structure

Keep the frontend and backend logically separate.

```text
tetherfi-speech-to-text/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── AudioUploader.jsx
│   │   │   ├── Transcript.jsx
│   │   │   ├── PerformanceMetrics.jsx
│   │   │   └── LanguageSelector.jsx
│   │   │
│   │   ├── hooks/
│   │   │   └── useAudioStreaming.js
│   │   │
│   │   ├── services/
│   │   │   └── websocket.js
│   │   │
│   │   ├── App.jsx
│   │   └── main.jsx
│   │
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes.py
│   │   │   └── websocket.py
│   │   │
│   │   ├── services/
│   │   │   ├── asr_service.py
│   │   │   ├── audio_service.py
│   │   │   └── metrics_service.py
│   │   │
│   │   ├── core/
│   │   │   └── config.py
│   │   │
│   │   └── main.py
│   │
│   └── requirements.txt
│
├── samples/
│   ├── english.wav
│   ├── mandarin.wav
│   └── indonesian.wav
│
├── tests/
│   ├── test_asr.py
│   ├── test_audio.py
│   └── load_test.py
│
├── reports/
│   ├── benchmark_results.csv
│   └── accuracy_results.csv
│
├── architecture/
│   └── architecture.png
│
└── README.md
```

## 7.1 Responsibility of each module

| File / component | Responsibility |
|---|---|
| `asr_service.py` | Loads Qwen3-ASR and provides transcription methods. It should not know how React displays the transcript. |
| `audio_service.py` | Audio validation, conversion, and processing. |
| `websocket.py` | Manages WebSocket connections and incoming audio chunks. |
| `metrics_service.py` | Collects performance measurements. |
| `AudioUploader.jsx` | Handles file selection. |
| `useAudioStreaming.js` | Manages frontend audio streaming logic. |
| `Transcript.jsx` | Displays recognized text. |
| `PerformanceMetrics.jsx` | Displays latency and other performance information. |
| `LanguageSelector.jsx` | Supports language selection if the implementation exposes that control. |

This structure demonstrates **separation of concerns**. Each module has a clearly defined responsibility, making the application easier to maintain, test, and extend.

---

# 8. Implementation roadmap

Complete the project in phases. Avoid attempting the entire application before verifying that the model works on the available CPU.

## Phase 1 – Environment and research

- [ ] Check CPU and RAM specifications.
- [ ] Install Python and Node.js.
- [ ] Understand the Qwen3-ASR model and available runtimes.
- [ ] Investigate CPU compatibility.
- [ ] Download and test the model.

**First priority:** Confirm that the required model can load and perform inference on the CPU machine.

## Phase 2 – Standalone ASR implementation

- [ ] Load Qwen3-ASR.
- [ ] Read a WAV file.
- [ ] Validate sample rate and channels.
- [ ] Run transcription.
- [ ] Test English, Mandarin, and Bahasa Indonesia samples.
- [ ] Measure inference time.

## Phase 3 – Backend development

- [ ] Create the FastAPI application.
- [ ] Implement REST endpoints where needed.
- [ ] Implement the WebSocket connection.
- [ ] Receive audio chunks.
- [ ] Integrate the ASR service.
- [ ] Return transcript updates.

## Phase 4 – Frontend development

- [ ] Build the React interface.
- [ ] Allow WAV file selection.
- [ ] Read audio progressively.
- [ ] Connect to the WebSocket.
- [ ] Display transcript updates.
- [ ] Display processing status and latency.

## Phase 5 – Full application integration

- [ ] Connect frontend and backend.
- [ ] Test the complete audio flow.
- [ ] Handle errors and disconnections.
- [ ] Test different chunk sizes.

## Phase 6 – Performance testing

- [ ] Measure latency.
- [ ] Measure CPU utilization.
- [ ] Measure RAM consumption.
- [ ] Calculate transcription accuracy.
- [ ] Test concurrent streams.

## Phase 7 – Research and optimization

- [ ] Investigate `whisper.cpp`.
- [ ] Compare CPU inference options.
- [ ] Investigate quantization.
- [ ] Analyze scaling strategies.

## Phase 8 – Submission preparation

- [ ] Create the architecture diagram.
- [ ] Write the README.
- [ ] Prepare the benchmark report.
- [ ] Prepare capacity estimates.
- [ ] Record the presentation and demonstration.

---

# 9. Performance measurements you must understand

The assignment does not require an advanced performance laboratory. It does require basic measurements and an explanation of what they mean.

## 9.1 Latency

Latency is the time taken for the system to produce a result. Measure at least two timings:

**First transcript latency:** Time from the defined start of audio processing until the first recognized text appears.

**Final transcription latency:** Time taken to finish processing the complete recording.

Hypothetical example only (not an expected result):

| Measurement | Example |
|---|---:|
| Audio duration | 10 seconds |
| First transcript latency | 2.5 seconds |
| Final transcription latency | 14 seconds |

### Real-Time Factor (RTF)

```text
RTF = Processing Time / Audio Duration
```

Example:

```text
RTF = 5 seconds / 10 seconds = 0.5
```

An RTF below 1 means processing is faster than the audio duration, provided both values use the same clearly defined processing interval.

## 9.2 CPU utilization

Observe how much CPU processing power the ASR application consumes.

Useful observations include:

- Idle CPU usage.
- CPU usage while loading the model.
- CPU usage during transcription.
- CPU usage with multiple streams.

The Python `psutil` library can be used to collect CPU utilization.

## 9.3 Memory consumption

Measure how much RAM is used by the backend and model.

Pay attention to:

- Memory required when loading the model.
- Memory during transcription.
- Memory consumption during concurrent processing.

Clearly state whether a measurement refers to the backend process, the model process, or the whole machine.

## 9.4 Accuracy

Prepare reference transcripts for each sample recording and compare the generated transcript with the expected text.

For English and Indonesian, use **Word Error Rate (WER)**:

```text
WER = (S + D + I) / N
```

Where:

- `S` = substitutions
- `D` = deletions
- `I` = insertions
- `N` = number of words in the reference transcript

For Mandarin, **Character Error Rate (CER)** is generally a more suitable character-based metric.

Normalize punctuation and text consistently before comparing results. Document the normalization approach so the comparison is understandable and repeatable.

## 9.5 Concurrency

Concurrency means processing multiple audio streams at the same time. Each stream represents a separate call leg.

Example:

- One user starts an audio stream.
- A second user starts another stream.
- A third user starts another stream.

Observe:

- Whether processing becomes slower.
- Whether CPU utilization increases.
- Whether memory consumption grows.
- Whether transcript updates remain responsive.
- Whether streams interfere with one another or fail.

> **Important:** Multiple WebSocket connections do not automatically mean multiple simultaneous model inferences. The backend must actually schedule, execute, and measure concurrent processing.

---

# 10. C++ inference and alternative ASR research

The assignment specifically asks you to investigate a C++-based inference option or runtime. A useful comparison candidate is **whisper.cpp**, a C/C++ implementation of OpenAI Whisper.

The guide identifies whisper.cpp as useful to investigate because it supports CPU-only inference, quantization, and multiple hardware optimizations.

### Initial comparison

| Feature | Qwen3-ASR | whisper.cpp |
|---|---|---|
| Model family | Qwen3-ASR | Whisper |
| CPU inference | Investigate and benchmark the selected runtime | Supported |
| C++ implementation | Not the primary official interface described in this guide | Yes |
| Multilingual | Yes | Yes |
| Quantization | Runtime-dependent | Supported |
| Role in assignment | Main required model | Alternative for comparison |

Qwen3-ASR supports the required English, Indonesian, and Chinese languages. whisper.cpp is also a relevant multilingual CPU alternative.

### What to compare

Run the same audio samples on both systems, using the same machine and comparable measurement conditions. Compare:

- Recognition accuracy.
- CPU usage.
- Memory consumption.
- Processing speed.
- Ease of integration.

Do not claim that one system is faster or more accurate until you have measured it under comparable conditions.

---

# 11. Load testing and server sizing

The assignment asks you to estimate the infrastructure required for:

- 50 concurrent call legs
- 100 concurrent call legs
- 200 concurrent call legs
- 500 concurrent call legs
- 1,000 concurrent call legs

You are **not** expected to run all these streams. Test as many simultaneous streams as your available machine can reasonably handle, then use the measurements to form estimates.

## 11.1 Record your test environment

Record:

- CPU model and number of cores / vCPUs.
- RAM.
- Operating system.
- ASR model and runtime.
- Maximum tested concurrent streams.
- Average latency at each concurrency level.
- CPU utilization and memory consumption.

For example, suppose a machine successfully handles 3 concurrent streams under your chosen performance criteria. This is only an illustrative example; replace it with your actual test result.

## 11.2 Initial capacity estimate

A rough linear starting calculation is:

```text
Required Capacity = Target Streams / Measured Streams
```

For example, if the measured baseline is 3 streams, use the ratio as an initial estimate for larger targets.

This is only a starting assumption. Real workloads do not always scale linearly.

Account for:

- Model memory overhead.
- CPU contention.
- Audio processing overhead.
- Network overhead.
- Concurrent request queues.
- Multiple model instances.
- Additional capacity for unexpected load.

## 11.3 Results and estimates table

Fill this table using actual test results. Do not invent measurements.

| Call legs | vCPU | RAM | Servers | Status |
|---:|---|---|---|---|
| Actual tested level (e.g. 3) | Measured | Measured | Measured | Tested |
| 50 | Estimate | Estimate | Estimate | Estimated |
| 100 | Estimate | Estimate | Estimate | Estimated |
| 200 | Estimate | Estimate | Estimate | Estimated |
| 500 | Estimate | Estimate | Estimate | Estimated |
| 1,000 | Estimate | Estimate | Estimate | Estimated |

Clearly label every value as **measured** or **estimated**, and explain the assumptions behind the estimates.

## 11.4 How could the application scale?

Understand these concepts:

1. **Load balancing:** Distributes incoming connections across backend servers.
2. **Message queues:** Manage incoming processing jobs.
3. **Multiple workers:** Process independent tasks concurrently.
4. **Horizontal scaling:** Adds more backend servers.
5. **Model serving:** Manages model loading and inference separately from application APIs.

One possible future architecture:

```text
Multiple frontend clients
          |
          v
     Load Balancer
       /       \
      v         v
Backend 1    Backend 2
       \       /
        v     v
   Audio Processing Queue
        /       \
       v         v
  ASR Worker 1  ASR Worker 2
```

This is a possible future architecture, not a requirement for the first working version.

---

# 12. Prepare for the interview

The goal is not merely to finish the assignment. You should be able to explain why you implemented each part of the system.

Prepare to answer the following questions in your own words. Base your answers on your actual implementation and measurements rather than memorizing generic answers.

## Architecture questions

1. Explain the architecture of your application.
2. Why did you separate the frontend and backend?
3. Why did you choose React and FastAPI?
4. What is the responsibility of each backend service?
5. How does the frontend communicate with the backend?
6. Why did you choose WebSocket instead of REST for streaming?

## Audio questions

7. What is Linear PCM?
8. What does a 16 kHz sample rate mean?
9. Why do we use mono audio?
10. How do you divide audio into chunks?
11. Why did you choose your chunk size?
12. How do you handle the final incomplete chunk?
13. What happens if the connection disconnects during streaming?

## AI/ML questions

14. What is ASR?
15. What is Qwen3-ASR?
16. What is inference?
17. How does the model convert audio into text?
18. Why did you choose the 0.6B model?
19. What is the difference between CPU and GPU inference?
20. What is model quantization?
21. What are the limitations of your chosen inference runtime?

## Performance questions

22. What is latency?
23. What is Real-Time Factor?
24. How did you measure CPU utilization?
25. How did you measure RAM usage?
26. How did you calculate WER?
27. Why did you use CER for Mandarin?
28. What happened when you increased concurrent streams?
29. What is the bottleneck in your application?
30. How would you support 1,000 concurrent call legs?

## Problem-solving questions

31. What was the most difficult part of the assignment?
32. What alternatives did you investigate?
33. What would you improve if you had another week?
34. How would you deploy this application?
35. What would happen if the ASR model failed?

---

# 13. Final submission checklist

The assignment identifies five main deliverable categories: source code, README, demo, short report, and architecture diagram. Use this expanded checklist to track the work.

- [ ] Complete frontend source code.
- [ ] Complete backend source code.
- [ ] Qwen3-ASR integration.
- [ ] English sample demonstration.
- [ ] Mandarin sample demonstration.
- [ ] Bahasa Indonesia sample demonstration.
- [ ] CPU-only benchmark results.
- [ ] Latency and memory measurements.
- [ ] Accuracy comparison.
- [ ] Concurrency testing.
- [ ] Server sizing estimates.
- [ ] Alternative ASR / C++ runtime investigation.
- [ ] Architecture diagram.
- [ ] README with installation and run instructions.
- [ ] Short technical report.
- [ ] Personal video presentation.

### What the short report should contain

- Hardware and operating system details.
- ASR model and runtime used.
- Implementation approach.
- Latency results.
- CPU and memory observations.
- Accuracy observations.
- Concurrency test results.
- Capacity estimates and assumptions.
- Limitations and conclusions.

### What the README should contain

- Prerequisites.
- Installation steps for frontend and backend.
- Model setup / download instructions.
- Configuration requirements.
- Commands to run the backend and frontend.
- How to run the sample demonstrations and tests.
- Known limitations.

---

# 14. Video presentation

The assignment requires you to personally appear and speak in the submitted video. Explain the work in your own words; a screen recording alone is not sufficient.

An approximately **8–12 minute** presentation is a reasonable target.

| Section | Suggested time |
|---|---:|
| Introduction | 1 minute |
| Problem and objective | 1 minute |
| Architecture and technologies | 2 minutes |
| Live application demonstration | 2 minutes |
| AI model and streaming explanation | 2 minutes |
| Performance results | 2 minutes |
| Challenges and future improvements | 1–2 minutes |

During the demonstration, do not only show that the application works. Explain what happens behind the scenes as the audio is processed.

Cover:

- What you built.
- How you approached the problem.
- Frontend, backend/API, and streaming flow.
- AI/ML model integration.
- Architecture and technologies used.
- Important technical decisions.
- Challenges and how you addressed them.
- Benchmark results.
- What you learned.
- What you would improve next.

---

# 15. Important assignment notes

Keep these original assignment expectations in mind:

- You must personally appear and speak in the submitted video and explain the work in your own words.
- A simple working solution is better than an over-complicated incomplete solution.
- The UI does not need to look production-ready.
- Open-source libraries, documentation, and AI coding assistants may be used, but you must be able to explain the code and decisions.
- If something does not work, document what you tried, what you learned, and what you would do next.
- Fresher candidates are not expected to already have professional AI/ML or speech-recognition experience.
- The expectation is that you research unfamiliar topics, build an end-to-end solution, understand the code, and explain your decisions.
- The evaluation focuses on how you learn, build, test, debug, measure, and reason.

---

# 16. Recommended order of work

For a manageable implementation, follow this order:

1. **Verify the machine and model first.** Record CPU/RAM details and prove that Qwen3-ASR can load and transcribe a sample on CPU.
2. **Build a standalone transcription script.** Validate the WAV format and test all three languages.
3. **Measure a baseline.** Record inference time, memory, CPU use, and accuracy before adding streaming complexity.
4. **Build the backend.** Add audio validation, stream state, WebSocket handling, and transcript messages.
5. **Build the frontend.** Add file selection, chunk generation, WebSocket communication, transcript display, and metrics.
6. **Integrate and test.** Verify progressive transmission, final-chunk handling, errors, and disconnections.
7. **Benchmark concurrency.** Increase the number of streams gradually and record what actually happens.
8. **Research alternatives.** Compare whisper.cpp or another suitable runtime using the same samples and machine.
9. **Prepare evidence.** Create the architecture diagram, report, README, sizing estimates, and presentation.

**Final principle:** Separate facts from assumptions. Report measured values as measured, estimates as estimates, and limitations honestly. A clear explanation of a simple working system is stronger than unsupported performance claims.
