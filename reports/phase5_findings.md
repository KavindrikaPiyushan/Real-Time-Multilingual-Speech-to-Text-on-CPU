# Phase 5 findings: integration, errors, chunk size and processing settings

Machine/model: see `phase1_findings.md` (i5-10500H, 24 GB, CPU only, Qwen3-ASR-0.6B-hf, float32). All streams are paced at real-time speed
(each chunk sent when its audio would have been spoken). Single stream, idle machine. Raw data: `chunk_size_results.csv`, `tuning_results.csv`.

## 1. Integration and error handling (tests)
| Test | Result |
|---|---|
| WebSocket protocol, 12 cases (`tests/test_ws_protocol.py`) | 12/12 pass |
| Fake-model unit tests of the streaming logic (`tests/test_stream_transcriber.py`) | 7/7 pass |
| Frontend logic run in Node against the live backend (`tests/frontend_check.mjs`) | 13/13 pass |
| Real server killed mid-stream -> client error `connection_lost` (`tests/failure_check.mjs`) | pass |
| Model cannot load -> health reports it, stream refused with `model_unavailable`, REST 503 | pass |
| Bad/unsupported audio, bad language, user pressing Stop, client disconnect -> clean error / server cleans the stream | pass |

Bug found and fixed during this phase: the `ASR_MODEL_ID` setting was ignored (`main.py` did not pass it to the model service).
Not yet verified: the React page itself was not exercised in a real browser by an automated test (only its logic modules were).

## 2. Chunk size (how audio is SENT), update interval 2 s, segment 10 s, 2 repetitions per cell
| Chunk | First text (English / Mandarin) | Final latency after end | Model time | Error rate |
|---|---|---|---|---|
| 0.5 s | 3.0 s / 3.2 s | 6.4 s / 4.0 s | 14.4 s / 16.5 s | same |
| 1 s | 3.2 s / 3.2 s | 5.9 s / 4.4 s | 14.3 s / 16.9 s | same |
| 2 s | 3.0 s / 3.0 s | 5.9 s / 3.7 s | 13.9 s / 15.9 s | same |
| 5 s | 7.4 s / 6.9 s | 4.0 s / 3.5 s | 7.4 s / 8.9 s | same |

Error rates were identical at every chunk size (English WER 0.353, Mandarin CER 0.000).
- Chunks of 0.5-2 s behave almost the same, because the server transcribes every 2 s of new audio regardless of chunk size.
  Chunk size (transport) and processing window/update interval (model work) are independent.
- 5 s chunks delay the first text by about 4 s (nothing can be transcribed before the first chunk exists) but halve the model work,
  because fewer updates are triggered.
- Chosen default: 2 s (good responsiveness, 64 KB per chunk, little overhead; larger chunks only delay the first text).

## 3. Processing settings (update interval / max segment), 2 s chunks, one run per cell
| Update / segment | Clip | First text | Final latency | Mean / max lag | Model time | RTF (model/audio) | Error rate |
|---|---|---|---|---|---|---|---|
| 2 s / 10 s (default) | English 11 s | 2.9 s | 6.1 s | 1.3 / 3.1 s | 14.0 s | 1.26 | WER 0.353 |
| 2 s / 10 s | Indonesian 52 s | 3.2 s | 7.6 s | 5.5 / 12.7 s | 56.9 s | 1.09 | WER 0.381 |
| 4 s / 10 s | English | 6.0 s | 5.6 s | 1.5 / 3.1 s | 10.6 s | 0.96 | WER 0.353 |
| 4 s / 10 s | Indonesian | 6.6 s | 7.6 s | 5.8 / 10.5 s | 54.4 s | 1.04 | WER 0.469 |
| 3 s / 6 s | English | 6.0 s | 3.3 s | 1.8 / 4.3 s | 8.3 s | 0.75 | WER 0.471 |
| 3 s / 6 s | Indonesian | 6.7 s | 3.7 s | 6.7 / 14.2 s | 49.2 s | 0.94 | WER 0.434 |
| 4 s / 6 s | English | 5.9 s | 3.2 s | 1.8 / 4.3 s | 8.2 s | 0.74 | WER 0.471 |
| 4 s / 6 s | Indonesian | 6.6 s | 2.6 s | 6.5 / 14.2 s | 47.9 s | 0.92 | WER 0.434 |

Lag = audio the server has received minus audio covered by the latest transcript. Single runs: differences of a few percent are within noise
(the same 2/10 Indonesian configuration scored WER 0.442 in the offline Phase 2 run and 0.381 here).

Observations
- **Dense speech nearly saturates the CPU even with one stream.** With 6 s segments the Indonesian clip's total model time (about 48 s)
  is close to one single offline pass over the whole clip (45 s in Phase 2), so redundant re-processing is not the main cost there. The cost follows the
  amount of speech (tokens generated), and this fast conversational clip needs about 0.9 s of compute per second of audio. Lag therefore stays around 10-14 s.
- **Redundancy matters more for sparse speech:** the English clip needs 14 s of model time at 2 s updates but 8 s at 6 s segments (RTF 1.26 -> 0.75).
- **Shorter segments hurt English accuracy** (WER 0.353 -> 0.471): cutting at a quiet point still splits some phrases, and less context is available.
- Longer update interval (4 s) cuts compute about 25% for English at the same accuracy, but doubles the time to first text (3 s -> 6 s).

## 4. Decision
- Keep the defaults: 2 s chunks, 2 s update interval, 10 s segments (best first-text latency and best English accuracy among the tested settings).
- For capacity testing in Phase 6, also run 4 s / 10 s, since it reduces compute per stream.
- A single stream already runs at roughly real-time cost on dense speech, so expect low concurrency on this laptop. This is measured in Phase 6, not assumed.
- Limitation to state honestly: partials lag behind the audio on dense speech (up to about 14 s on the 52 s Indonesian clip). Application-level streaming
  with an offline model trades latency for simplicity; native streaming (vLLM) or a faster runtime (Phase 7) would be the next step.
