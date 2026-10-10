# Audio in Image

Choose **Audio in Image**, upload a cover and audio, click **Embed**, and download `audio-in-image.png`. In the same mode's **Decode** tab, upload that PNG and click **Decode** to listen and download the recovered audio. No reference or original cover is required. Existing Image in Audio ZIPs use their original mode and remain compatible.

You can choose **Record audio** instead of an upload to capture a personal message. Allow browser microphone access, speak, stop, review and embed. A stopped recording is supplied as 16-kHz WAV and goes through the same bounded preparation and saved-PNG verification. Switching back to Upload audio explicitly selects a file instead of the recording. Microphone recording requires HTTPS or localhost; the stopped recording is uploaded to the host for processing. Send the resulting PNG unchanged as an original file/document and share the app link so the recipient can decode and listen. Implementation uses the official [Streamlit audio input](https://docs.streamlit.io/develop/api-reference/widgets/st.audio_input).

## Automatic preparation

The existing bounded FFmpeg conversion accepts WAV, MP3, FLAC, M4A, AAC, OGG, Opus, AIFF and WMA, depending on codecs. Audio is limited to 24,000,000 bytes and 180 seconds and converted to mono 16 kHz with headroom. It is encoded as Ogg Opus at 48 kbps constant bitrate by default; Advanced options offers 32, 48 or 64 kbps. Opus is lossy. Exact recovery means the saved compressed audio bytes match, not the original recording's samples or file bytes. The WAV player decodes the recovered payload for browser compatibility.

Cover inputs support PNG, JPEG, WebP, BMP, TIFF, GIF, ICO and AVIF up to 16 megapixels. The first frame/page is oriented and converted to 8-bit RGBA. Output is a PNG at most 5 megapixels and 24 MB. Too-small covers are enlarged automatically; oversized covers are reduced. Extreme aspect ratios are bounded to 64:1 and dimensions to 8192 pixels. Displayed dimensions describe the actual output. Disable automatic resizing to require sufficient capacity in the original dimensions.

## Embedded format v1

RGB samples are traversed row-major, R then G then B. Each sample's lowest bit holds one packet bit; bytes use most-significant bit first. Alpha samples are excluded and preserved exactly relative to the prepared cover. An RGB sample changes by at most 1 on the 0–255 scale relative to that cover. Resizing may change pixels much more; this bound describes the embedding operation only.

The packet is 8-byte ASCII magic `AWIMG001`, a 4-byte unsigned little-endian Opus byte length, 32-byte SHA-256 digest, followed by Ogg Opus bytes. The 44-byte header is embedded in pixels as well. The maximum audio payload is 2,000,000 bytes. Capacity is floor(3 × width × height / 8) minus 44 bytes. No PNG audio metadata or appended file is used. Decoding validates the format, bounded length, available capacity, hash and audio decoding before success. Embedding saves and reloads the PNG, recovers the audio and compares exact payload bytes before offering download.

The format is deliberately independent of the old Haar/FFT audio-watermark reference. It is conventional LSB steganography, not a claimed research breakthrough. The unkeyed digest detects accidental corruption; an attacker can replace the payload and digest. Anyone with this app can decode it. Resizing, JPEG conversion, colour edits, screenshots and automatic picture compression can destroy recovery. Send the downloaded PNG unchanged as an original file/document.

## Earlier controls

The shared `advanced.py` renderer keeps the earlier lab's source selection, gain, generated image/text payloads, Haar decomposition/subbands, strength, blocks, saved PCM16 recovery, waveforms/spectra, attacks/batch exports, block measurements, candidate WAV/reference extraction and method notes. `lab.py` runs the same renderer standalone. These are independent experiments; their controls do not silently change either automatic mode. Historical lab attack findings are unchanged and do not establish robustness of audio in PNG.

Implementation references: [FFmpeg libopus options](https://ffmpeg.org/ffmpeg-codecs.html#libopus) and [Streamlit expander](https://docs.streamlit.io/develop/api-reference/layout/st.expander), checked 2026-10-10. Validation and live deployment observations are recorded in `VALIDATION.md` and `../deployment/hosting-status.json`.
# Current default: full quality

The app now defaults to a private PNG audio attachment that preserves full image dimensions and decoded 8-bit RGBA pixels. It does not use the RGB-LSB method described below. That earlier pixel-steganography method remains in Advanced options, and existing PNGs still decode. See [FULL_QUALITY.md](FULL_QUALITY.md) for the current default, exact scope and limits.

