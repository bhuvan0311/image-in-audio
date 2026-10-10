# Full-quality image embedding

The default was changed after a 399 × 501 photograph became a 25 × 32 PNG in the earlier automatic DSP mode. That mode repeatedly resized to fit at most 8,192 bytes and the actual audio capacity. Enlarging its preview cannot restore lost detail.

The new default never resizes or edits the decoded image pixels. Inputs are bounded to 16 megapixels and converted to oriented 8-bit RGBA PNG (first frame/page). JPEG decoding preserves its existing pixels without another lossy compression pass; original JPEG bytes, animation, all metadata, 16-bit colour and HDR are not guaranteed. Uploads and finished files must fit within 24,000,000 bytes; oversized output errors rather than silently shrinking.

## Image in Audio

A private `imAg` RIFF chunk holds the full PNG inside a PCM24 WAV. The RIFF size and odd-byte padding include the attachment. Prepared audio sample bytes remain unchanged. Its payload begins with `AWFULL01`, a little-endian uint32 byte length and SHA-256 digest, followed by PNG bytes. The WAV decodes by itself. The familiar ZIP carries that WAV and a small `image-in-wav-chunk-v1` reference; no separate image sidecar exists. Earlier `image-in-audio-v1` reference-based DSP ZIPs still decode.

## Audio in Image

A private ancillary `auDi` PNG chunk stores the same version/length/hash packet followed by Ogg Opus bytes. It appears before IEND. Existing image chunks are unchanged, preserving the prepared PNG's dimensions, decoded RGB and alpha exactly. PNG CRCs, packet length/hash and actual audio decoding are checked before success. Existing `AWIMG001` RGB-LSB PNGs remain supported. Audio retains the prior mono-16-kHz lossy Opus preparation and bitrate settings.

## Interpretation and sharing

This is file embedding through container attachments, not concealment in audio samples or image pixels. Private chunks can be inspected or removed; editing/re-encoding or messaging-service compression can strip them. Send the original WAV/ZIP/PNG as a file/document. The digest detects accidental corruption; it does not encrypt or authenticate the payload. The earlier DSP/LSB methods remain explicit choices under Advanced options, with their original capacity and resizing behavior.

Format references: [PNG specification](https://www.w3.org/TR/png-3/) and [Microsoft RIFF overview](https://learn.microsoft.com/en-us/windows/win32/xaudio2/resource-interchange-file-format--riff-). New chunk identifiers and packet formats are application-specific.
