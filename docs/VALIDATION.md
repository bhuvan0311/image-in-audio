# Validation evidence · 2026-10-10

Measured on Windows 11 with Python 3.12.14. See `results/environment.json` for the actual library and ffmpeg versions, `results/experiments.csv`/`.json` for every experiment, and the JUnit reports for tests. Re-run commands are in the README. Signal/payload generation and attack seeds are fixed; time varies with load and scheduling. MP3 results also depend on the codec version. No MATLAB or board runtime was validated.

## Saved example

The generated two-second 16 kHz harmonic signal carries an 8×8 checkerboard (64 bits) in A2 at level 2, strength 0.06. The exported PCM16 WAV was reloaded before extraction. A separate CLI execution read the WAV and reference from disk and recovered the same bit vector.

| Metric | Actual result |
|---|---:|
| BER | 0 |
| Exact payload recovery | Yes |
| Audio SNR | 34.51556 dB |
| Peak amplitude | 0.4132080078125 |
| Clipped samples | 0 |
| Raw capacity | 3999 bits |
| Watermarked WAV size | 64,044 bytes |
| Reference JSON size | 4,739 bytes |
| Full pipeline time in exported example | 14.532 ms |

The separately quantized `original.wav` is a listening convenience. SNR in the metrics compares the original prepared float array with saved/reloaded watermarked audio. Thus independently computing SNR between the two exported WAVs can give a slightly different value. This reference/display distinction is explicit in the bundle README.

## Attack suite

Two generated signals × two strengths × three subbands × eleven transformations × two candidate kinds = **264 rows**. Each transformation is applied to a marked signal and a separately saved/reloaded unwatermarked control. All transformation outputs are saved as PCM16 and reloaded again before decoding; PCM8/24 rows therefore include the requested intermediate quantization followed by the common PCM16 transport. The resampling experiment is a 3/4 downsample and 4/3 return, using polyphase anti-aliasing and deterministic duration trimming; it is not a rate-mismatched extraction claim. Noise is Gaussian with a fixed seed and RMS-derived target SNR (45/25 dB); at silence a declared 0.1 nominal RMS sets its scale. Low-pass uses a sixth-order 2 kHz Butterworth, zero-phase forward/backward filtering. Crop removes the first max(1, floor(N/100)) samples. MP3 is encoded with ffmpeg/libmp3lame at 128 kbps then decoded. No alignment repair is applied after MP3.

| Transformation | Marked exact recoveries / 12 attempted | Unwatermarked detections / extractable controls |
|---|---:|---:|
| No attack | 12 / 12 | 0 / 12 |
| Noise 45 dB | 12 / 12 | 0 / 12 |
| Noise 25 dB | 12 / 12 | 0 / 12 |
| Gain 0.8 | 11 / 12 | 0 / 12 |
| Gain 1.1 | 12 / 12 | 0 / 12 |
| Resample round trip | 8 / 12 | 0 / 12 |
| Low-pass 2 kHz | 4 / 12 | 0 / 12 |
| Crop first 1% | 0 / 12 | 0 / 0 (all extraction failures) |
| Intermediate PCM8 | 12 / 12 | 0 / 12 |
| Intermediate PCM24 | 12 / 12 | 0 / 12 |
| MP3 128 kbps | 8 / 12 | 0 / 12 |

There are **103 exact recoveries / 132 marked attempted rows (78.03%)**, or 103/120 extractable rows (85.83%). This includes the no-attack condition. Twelve cropped marked rows fail the length/alignment requirement and retain null BER/SNR, not zero BER. Seventeen other marked rows produce incorrect bits. There are zero detections / 120 extractable balanced-payload controls; twelve cropped controls cannot be decoded. These empirical controls are limited to these signals, parameters and expected balanced image. The all-zero expected-payload/silent-control false positive is separately demonstrated by an automated check. Zero balanced-control detections do not prove authenticity or a universal false-positive rate.

## Desktop block measurements

Each run processes the same two-second 16 kHz generated harmonic signal, distributing 64 bits across independent blocks. Time includes DWT, FFT editing, inverse transforms and reference-record construction in the embedding loop. Saving/reloading/extracting is validated separately and excluded from per-block embedding time. Every listed run recovered the saved PCM16 payload exactly.

| Block samples | Mean / max processing (ms) | Nominal audio duration (ms) | Largest time/duration ratio | Estimated array bytes |
|---|---:|---:|---:|---:|
| 256 | 1.462 / 97.875 | 16 | 6.117 | 7,912 |
| 1024 | 0.538 / 1.385 | 64 | 0.0216 | 29,200 |
| 4096 | 3.267 / 9.381 | 256 | 0.0366 | 109,072 |

The 256-sample measurement has a maximum processing time longer than the block's audio duration. It is retained rather than replaced with a favorable run. This single-pass desktop data is affected by concurrent work, warm-up, allocation and scheduling. It is not a latency guarantee or an ESP32/STM32 benchmark. Array estimates use float64 input/output/DWT, complex128 spectra and reference/directions, plus int64 bin indices. They exclude interpreter/UI/metadata, full-file storage, library scratch and process overhead; they are not peak RSS or MCU RAM requirements. No real-time audio I/O is implemented.

Optional C parity: **NOT RUN** because no suitable compiler was found in the inspected environment. The complete Python lab works without it. No embedded port was flashed or tested.

## Automated and interface verification

Final unified run: **302 passed in 20.07 seconds**, zero failures/errors/skips. The additional application regression checks source switching, preserved completed results and exact UTF-8 recovery. Browser WAV/reference upload and an uploaded-audio UTF-8 embedding run also completed successfully.

The final test counts and browser-walkthrough record are maintained in `PROGRESS.md` and `screenshots/README.md`. The engine checks include 243 supported-range saved-PCM16 recovery cases; no-watermark reconstruction including odd lengths; exact/overflow capacity; independent pairwise Haar and cosine/DFT fixtures; conjugate symmetry and Parseval energy; waveform length; finite/amplitude constraints; malformed audio/WAV/reference metadata; explicit stereo handling; independent BER/SNR/peak/clipping formulas; PCM8/16/24 quantization bounds; seeded transformations; unwatermarked controls and the degenerate detector hazard; block recovery; and archive/CSV/JSON consistency. Streamlit application tests exercise actual embedding, block measurements and the full batch, not mocked metrics.

Recovery is required only inside the baseline operating range in `ALGORITHM.md`. Every attack result, including failures, remains in the raw exports. UI screenshots are observations of the running application, not generated mockups. Container/public-host deployment, perceptual listening studies, a blind method, cryptographic signing and hardware measurements are outside completed validation.

The preceding scope describes the initial lab validation. Public-host validation was subsequently completed on 2026-10-10 as recorded below; container execution remains untested.

## Automated image app update

The earlier 302-check result above describes the original lab. The updated app and lab passed **338 unified checks**; an additional final media-only run passed **36 checks** after the FFmpeg input-format restriction. Reports: `results/tests.xml`, `results/media-tests.xml`. Eight advertised image formats and nine audio formats were converted and exercised with actual saved-WAV image recovery. See `SIMPLE_APP.md` for the new representation, limits, signed-zero repair and validation scope. A real browser PNG/MP3 embed/download/ZIP-upload/decode/playback walkthrough succeeded. Historical 64-bit attack figures remain unchanged and do not validate robustness of larger full-colour payloads.

## Public-host validation — 2026-10-10

Streamlit Community Cloud deployment at https://image-in-audio-bhuvan0311.streamlit.app/ was verified with a built-in example and uploaded generated PNG/stereo MP3. The actual hosted ZIP was downloaded, uploaded into the hosted decoder, decoded successfully and played in the browser. Playback advanced from 0.032 to 5.562846 seconds with no media error in the 8-second WAV. The downloaded recovered PNG SHA-256 was `8d43d3ffc9976759098fd95d99fc36e4f373cb753687c54eba8cee851bf29e5e`, matching the input. The hosted embedding reported zero bit errors and zero clipping. Independent offline extraction from the downloaded ZIP succeeded without supplying an original image (`results/hosted-download-check/verification.json`). Public sharing was checked in the provider's Share dialog. See `deployment/hosting-status.json` for runtime and workflow observations and `screenshots/07-hosted-decode.jpg` for actual live recovery. Full codec coverage on Linux, load tests and uptime guarantees are not established by this walkthrough.

## Bidirectional app and preserved advanced lab — 2026-10-10

The updated complete suite passed **376 tests in 330.90 seconds**, with zero failures, errors or skips (`results/bidirectional-tests.xml`). This includes all earlier checks and 38 new Audio in Image checks: saved PNG recovery with an independent pixel-bit reader, playable recovered WAV, one-level RGB changes and untouched alpha relative to the prepared cover, eight cover formats, nine stereo audio formats, 32/48/64 kbps settings, disabled resizing, extreme aspect ratios, maximum 180-second recording, damaged/header/length/crop/JPEG/plain-image rejection, input and setting rejection, both automatic modes and the shared advanced lab. Historical attack outputs and calibration findings remain unchanged.

The first test run encountered two harness setup/teardown errors because a 24-MB byte fixture generated a test name longer than Windows' environment-variable limit. Explicit short case names repaired this; the complete final run passed. These errors did not arise in the app. A real local browser displayed verified Audio in Image embedding and all earlier controls inside Advanced options. `results/audio-in-image-example/` contains a saved PNG and independently recovered audio; decoding supplied no original cover, recording or reference.

The updated public host was also verified with uploaded PNG/stereo MP3, a 362 × 361 pixel output PNG, real PNG download/re-upload, hosted decode, audio playback and Opus/WAV downloads. Playback started with `paused=false`, readyState 4 and no media error and advanced through the 8-second recording. The downloaded Opus SHA-256 `c6e4bd3396fe08ee6961f0139f2cd10f98ab6941d49dcfc82da75759cabbf069` matched the payload independently recovered from the hosted PNG (`results/hosted-audio-image-check/verification.json`). Exact equality concerns the compressed Opus payload; PCM produced by different FFmpeg/Opus versions need not be byte-identical. The hosted advanced experiment reported BER 0%, exact recovery Yes and zero clipping. An actual ZIP from the previous deployment decoded successfully, and the original automatic example passed. Screenshots `08-hosted-audio-in-image.jpg` and `09-hosted-advanced-options.jpg` show actual hosted results. Source commit: `ccc9e0809ce60e76f8460b6c16081de30a4d6935`.

## Personal audio recording — 2026-10-10

Added native 16-kHz Streamlit microphone input alongside explicit audio uploads in both automatic modes, plus a recording source in the shared advanced lab. The final focused suite passed **10 tests in 49.97 seconds**, no failures/errors/skips (`results/recording-tests.xml`); it includes six recording checks plus the existing mode, demo and advanced-interface regression checks. Tests supply a generated WAV at the recorder's return boundary; the actual media preparation, embedding, saved-file verification and decoding execute normally. They cover both embedding directions, source switching, empty/invalid recordings, rendering the native recorder and advanced recorded-WAV embedding. The independent advanced recording run also passed (`results/advanced-recording-tests.xml`). No engine or payload format was changed; the preceding 376-test full-suite record remains historical.

These tests do not capture a physical microphone or establish browser/device compatibility. Browser microphone permissions must be granted by each visitor, and denied/unavailable microphones retain the upload alternative. The public HTTPS host's embedding iframe was observed to allow microphone use. Live widget/deployment observations are recorded in `../deployment/hosting-status.json`.

Published and remote-verified source commit `cf1528db6188c3d290dfe6af26492e01a9624c23` to the authorized public repository and existing free HTTPS app. The live native recorder was observed in Image in Audio, Audio in Image and the advanced lab; empty recording actions were disabled and upload alternatives remained available. Actual live proof: `screenshots/10-hosted-record-audio.jpg`. No physical microphone audio was captured during verification. Deployment history and scope are preserved in `../deployment/hosting-status.json`.

## Full-resolution default — 2026-10-10

The reported files were checked locally: the original JPEG was 399 × 501, but the earlier embedded PNG was 25 × 32. The old DSP capacity/resizing policy caused real detail loss; increasing preview width alone cannot restore it. Full quality now uses a full-resolution PNG attachment inside WAV, and a private audio attachment inside PNG for the reverse direction. Neither default resizes or edits decoded image pixels. Audio preparation/compression remains bounded and explicitly disclosed. The experimental sample watermark and pixel steganography remain under Advanced options with their original behavior. Existing downloads remain decodable.

The user's original JPEG was converted locally to a 399 × 501 PNG and its decoded RGBA pixels matched exactly. The user's image was not uploaded to the public host or source repository for testing. Default previews fill the available width. Source-format/metadata/16-bit/HDR byte identity is not claimed; full quality preserves the decoded oriented 8-bit RGBA image, first frame/page only, within 16 megapixels and 24 MB finished output. Full-quality embedding is container storage, not a new watermark, encryption or research breakthrough.

The final affected-path suite passed **98 tests in 260.67 seconds**, with zero failures/errors/skips (`results/full-quality-tests.xml`). It includes independent RIFF/PNG packet reads, exact 399 × 501 image-pixel comparisons in both directions, untouched prepared WAV sample bytes, a tiny transparent cover without enlargement, corrupted/duplicate/truncated chunk rejection, reference ZIP round trip, explicit legacy method selection, all previous media/pixel-mode checks and recording/advanced controls. Seven expected SciPy warnings report that its audio reader skips the application-specific non-audio RIFF chunk; playback samples and attachment decoding passed. Historical engine/attack validation remains unchanged.
