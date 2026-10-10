# Image & Audio Lab

Live public app: https://image-in-audio-bhuvan0311.streamlit.app/

Choose **Image in Audio** or **Audio in Image**, upload an image and audio, and click Embed. **Full quality is the default**: the image keeps its original resolution and decoded 8-bit RGBA pixels. Image in Audio attaches a lossless PNG inside a playable WAV and downloads a WAV/reference ZIP; the WAV also decodes by itself. Audio in Image attaches compressed audio inside a PNG without changing its image pixels. Decode the downloaded WAV/ZIP or PNG in the corresponding mode, then play and download the result. Previews fill the available page width.

Both modes offer **Upload audio** and **Record audio**. For a personal message, choose Record audio, allow browser microphone access, speak, stop, preview and click Embed. Recordings need HTTPS or localhost and obey the same 3-minute/24-MB bounds. The recording is uploaded to the host after stopping. To share, send the downloaded PNG unchanged as an original file/document and the app link; the recipient uses Audio in Image → Decode. The app does not send messages to recipients automatically.

**Advanced options** preserves the earlier DSP watermark and RGB-LSB pixel steganography methods plus the full DSP lab: audio source, gain, binary image/text payload, Haar subband and level, FFT strength, blocks, waveform/spectrum inspection, controlled attacks, reproducible batch, block timing and reference-based extraction. Experimental methods may resize images to fit their capacities. Full quality never resizes. Audio in Image also offers 32/48/64 kbps quality.

## Deploy

Use Streamlit Community Cloud with `app.py` as the entry point and Python 3.12. Keep `requirements.txt` and `packages.txt` at the repository root. FFmpeg is required and installed through `packages.txt`. See `docs/HOSTING.md`.

## Check

In either mode, click **Try a ready-made example**, download the result, then upload it in that mode's **Decode** tab and click **Decode**. Expect verified recovery and playable audio. PNG decoding needs no original image or reference file. Existing Image in Audio ZIPs remain supported.

## Limits

Uploads and finished outputs: 24 MB each. Audio: up to 180 seconds, converted to mono 16 kHz. Full-quality images: up to 16 megapixels, decoded 8-bit RGBA, first frame/page only; JPEG becomes lossless PNG without another JPEG compression pass. Original source file bytes and 16-bit/HDR fidelity are not promised. Audio in Image uses lossy Opus compression (48 kbps default); recovered Opus bytes are exact, not the original recording/file. Experimental DSP images have an 8,192-byte payload and may shrink substantially; experimental LSB PNGs have a 5-megapixel carrier limit. See `docs/FULL_QUALITY.md` and `docs/AUDIO_IN_IMAGE.md` for the formats.

Advertised formats are PNG, JPEG, WebP, BMP, TIFF, GIF, ICO and AVIF; WAV, MP3, FLAC, M4A, AAC, OGG, Opus, AIFF and WMA. Actual support depends on installed codecs. Unsupported, corrupted and DRM-protected inputs can fail.

Keep the downloaded WAV/reference or PNG unchanged. Conversion, editing and messaging-service recompression can strip attachments or destroy experimental payloads. Full quality uses private RIFF/PNG chunks inside the file container; it is file embedding, not DSP watermarking or pixel steganography. Experimental methods remain available and older ZIP/PNG downloads still decode. Neither method is encryption or authenticated communication. The unkeyed hash detects corruption but does not authenticate hostile files. The ZIP contains no image sidecar.

Uploads are processed by the host. Audio conversion uses temporary files removed after processing; the app adds no permanent upload store. Results remain in the Streamlit session. Public hosting does not itself guarantee confidentiality.
