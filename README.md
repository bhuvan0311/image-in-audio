# Image & Audio Lab

Live public app: https://image-in-audio-bhuvan0311.streamlit.app/

Choose **Image in Audio** or **Audio in Image**, upload an image and audio, and click Embed. Settings are automatic. Image in Audio downloads a WAV plus reference ZIP; Audio in Image downloads one PNG that contains the compressed audio in its pixels. Decode the downloaded ZIP or PNG in the corresponding mode, then play and download the result.

**Advanced options** preserves the full earlier DSP lab: audio source, gain, binary image/text payload, Haar subband and level, FFT strength, blocks, waveform/spectrum inspection, controlled attacks, reproducible batch, block timing and reference-based extraction. These settings apply to the advanced experiment independently of the automatic modes. Audio in Image also offers 32/48/64 kbps quality and optional automatic resizing.

## Deploy

Use Streamlit Community Cloud with `app.py` as the entry point and Python 3.12. Keep `requirements.txt` and `packages.txt` at the repository root. FFmpeg is required and installed through `packages.txt`. See `docs/HOSTING.md`.

## Check

In either mode, click **Try a ready-made example**, download the result, then upload it in that mode's **Decode** tab and click **Decode**. Expect verified recovery and playable audio. PNG decoding needs no original image or reference file. Existing Image in Audio ZIPs remain supported.

## Limits

Uploads: 24 MB each. Audio: up to 180 seconds, converted to mono 16 kHz. Image in Audio uses PCM24 WAV and an image payload up to 8,192 bytes. Audio in Image uses lossy Opus compression (48 kbps default) and an output PNG up to 5 megapixels. Cover inputs: up to 16 megapixels, 8-bit RGBA, first frame/page only. Automatic resizing and the resulting dimensions are shown. Audio recovery is exact for the compressed Opus bytes, not for the original recording/file. See `docs/AUDIO_IN_IMAGE.md` for the pixel format.

Advertised formats are PNG, JPEG, WebP, BMP, TIFF, GIF, ICO and AVIF; WAV, MP3, FLAC, M4A, AAC, OGG, Opus, AIFF and WMA. Actual support depends on installed codecs. Unsupported, corrupted and DRM-protected inputs can fail.

Keep the downloaded WAV/reference or PNG unchanged. Resizing, recompression, edits and screenshot copies can destroy the payload. Image in Audio is reference-dependent watermarking; Audio in Image is self-contained pixel steganography. Neither is encryption or a guarantee of inaudibility, attack resistance or authenticated communication. The unkeyed hash checks corruption but does not authenticate hostile files. The Image in Audio ZIP contains no image sidecar; Audio in Image stores audio in RGB sample LSBs, not in PNG metadata or an appended file.

Uploads are processed by the host. Audio conversion uses temporary files removed after processing; the app adds no permanent upload store. Results remain in the Streamlit session. Public hosting does not itself guarantee confidentiality.
