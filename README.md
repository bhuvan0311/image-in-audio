# Image in Audio

Upload an image and an audio file, click Embed and download the watermarked WAV plus reference ZIP. Upload that ZIP in Decode to recover the verified image and play the audio. DSP settings are automatic.

## Deploy

Use Streamlit Community Cloud with `app.py` as the entry point and Python 3.12. Keep `requirements.txt` and `packages.txt` at the repository root. FFmpeg is required and installed through `packages.txt`. See `docs/HOSTING.md`.

## Check

Click **Try a ready-made example**, download **audio + reference ZIP**, then upload it in **Decode** and click **Decode**. Expect a verified image and playable audio. No original image is needed for decoding.

## Limits

Uploads: 24 MB each. Audio: up to 180 seconds, converted to mono 16 kHz PCM24 WAV. Images: up to 16 megapixels, converted to 8-bit RGBA PNG; first frame/page only. Large images are resized to fit up to 8,192 payload bytes. The embedded image size is shown.

Advertised formats are PNG, JPEG, WebP, BMP, TIFF, GIF, ICO and AVIF; WAV, MP3, FLAC, M4A, AAC, OGG, Opus, AIFF and WMA. Actual support depends on installed codecs. Unsupported, corrupted and DRM-protected inputs can fail.

Keep the downloaded WAV unchanged and retain its matching reference. This is reference-dependent watermarking, not encryption or a guarantee of inaudibility or attack resistance. The unkeyed hash checks recovery but does not authenticate hostile files. The ZIP does not contain an image file; recovery uses embedded audio samples and the reference.

Uploads are processed by the host. Audio conversion uses temporary files removed after processing; the app adds no permanent upload store. Results remain in the Streamlit session. Public hosting does not itself guarantee confidentiality.
