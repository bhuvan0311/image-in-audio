"""Two automatic media-hiding modes with the complete advanced DSP lab."""
import streamlit as st
from watermark_lab.media import create_image_audio, decode_image_audio, download_bundle, read_bundle, demo_inputs
from watermark_lab.audio_image import create_audio_image, decode_audio_image
from watermark_lab.full_quality import create_full_image_audio, create_full_audio_image, decode_full_image_audio

st.set_page_config(page_title="Image & Audio Lab", page_icon="🎵", layout="centered")
st.title("Image & Audio Lab")
st.write("Hide an image in audio, or audio in an image. Embed, download and recover in a few clicks.")
mode = st.radio("What would you like to hide?", ["Image in Audio", "Audio in Image"], horizontal=True, key="hiding_mode")


def audio_source(prefix, upload_key):
    choice = st.radio("Choose audio source", ["Upload audio", "Record audio"],
                      horizontal=True, key=f"{prefix}_audio_source")
    if choice == "Upload audio":
        return st.file_uploader("Audio or song", key=upload_key,
            help="WAV, MP3, FLAC, M4A, AAC, OGG, Opus, AIFF or WMA. Up to 24 MB and 3 minutes; no DRM.")
    st.caption("Press the microphone to start, then stop when finished. Allow microphone access if your browser asks. Keep your message under 3 minutes.")
    audio = st.audio_input("Record a personal message", sample_rate=16000,
                          key=f"{prefix}_recording",
                          help="The stopped recording is uploaded to this app for processing. You can listen before embedding. If your microphone is unavailable, switch to Upload audio.")
    if audio is not None:
        st.write("Your recording")
        st.audio(audio.getvalue(), format="audio/wav")
        st.caption("Recording ready. Click Embed to use this message with your image.")
    return audio


def render_image_in_audio():
    embed_tab, decode_tab, help_tab = st.tabs(["Embed", "Decode", "Help"])

    with embed_tab:
        st.write("Add your image and audio, then click Embed. The app chooses the settings and checks the saved result.")
        image = st.file_uploader("Image", key="image_upload", help="PNG, JPEG, WebP, BMP, TIFF, GIF, ICO and AVIF. First frame/page only. Maximum 16 megapixels.")
        audio = audio_source("image_in_audio", "simple_audio_upload")
        experimental = st.session_state.get("image_storage", "Full quality") == "DSP watermark"
        st.caption("Experimental DSP mode may shrink images to fit its small capacity." if experimental else
                   "Full quality: the image keeps its original resolution and pixels. It is stored as an attachment inside the WAV file. Audio becomes mono, 16 kHz WAV.")
        submit = st.button("Embed", type="primary", disabled=image is None or audio is None)
        demo = st.button("Try a ready-made example")
        if submit or demo:
            try:
                with st.spinner("Preparing files, embedding and checking the downloaded audio…"):
                    a, i = demo_inputs() if demo else (audio.getvalue(), image.getvalue())
                    result = create_image_audio(a, i) if experimental else create_full_image_audio(a, i)
                    result["bundle"] = download_bundle(result)
                    st.session_state["image_run"] = result
            except ValueError as exc:
                st.error(str(exc))
        if "image_run" in st.session_state:
            run = st.session_state["image_run"]
            info = run["image_info"]
            st.subheader("Last completed embedding")
            st.success("Verified: the image recovered from the saved audio matches exactly.")
            st.image(run["image"], caption=f"Image embedded: {info['embedded_size'][0]} × {info['embedded_size'][1]} pixels", width="stretch")
            if run.get("storage") == "file attachment":
                st.info("Original resolution and image pixels preserved. The image is attached inside the WAV; this is file embedding, not a DSP watermark.")
            if info["resized"]:
                st.info(f"Resized from {info['original_size'][0]} × {info['original_size'][1]} to fit the audio. Recovery is exact for the image shown here.")
            if info["first_frame_only"]:
                st.info("Only the first frame/page of the uploaded image was embedded.")
            st.download_button("Download full-size embedded image", run["image"], "embedded.png", "image/png")
            st.write("Audio with embedded image")
            st.audio(run["audio"], format="audio/wav")
            st.download_button("Download audio + reference ZIP", run["bundle"], "image-in-audio.zip", "application/zip", type="primary")
            with st.expander("Separate files and verification"):
                st.download_button("Download watermarked WAV", run["audio"], "watermarked.wav", "audio/wav")
                st.download_button("Download reference", run["reference"], "reference.json", "application/json")
                st.write("Prepared audio before embedding")
                st.audio(run["original_audio"], format="audio/wav")
                st.json({"image_bytes": info["byte_length"], "bit_errors": 0, "clipping_count": run["metrics"]["clipping_count"],
                         "snr_db": run["metrics"]["snr_db"], "duration_seconds": run["audio_info"]["duration_seconds"]})

    with decode_tab:
        st.write("Upload the WAV or ZIP downloaded after Embed, then click Decode. Older DSP watermark files require their matching reference.")
        bundle = st.file_uploader("Audio with image (WAV or ZIP)", type=["wav", "zip"], key="bundle_upload")
        with st.expander("Use separate WAV and reference files"):
            marked = st.file_uploader("Watermarked WAV", type=["wav"], key="marked_upload")
            reference = st.file_uploader("Reference JSON", type=["json"], key="reference_upload")
        st.caption("Full-quality WAVs decode on their own. Keep the matching reference for older DSP watermark files; it is not an encryption key.")
        if st.button("Decode", type="primary", disabled=bundle is None and (marked is None or reference is None)):
            try:
                with st.spinner("Recovering and verifying image…"):
                    if bundle is not None and bundle.getvalue().startswith(b"RIFF"):
                        st.session_state["image_decoded"] = decode_full_image_audio(bundle.getvalue())
                    else:
                        a, r = read_bundle(bundle.getvalue()) if bundle is not None else (marked.getvalue(), reference.getvalue())
                        st.session_state["image_decoded"] = decode_image_audio(a, r)
            except ValueError as exc:
                st.error(str(exc))
        if "image_decoded" in st.session_state:
            recovered = st.session_state["image_decoded"]
            st.subheader("Last completed decode")
            st.success("Image recovered and verified.")
            st.image(recovered["image"], caption="Recovered image — original embedded resolution", width="stretch")
            st.audio(recovered["audio"], format="audio/wav")
            st.download_button("Download recovered image", recovered["image"], "recovered.png", "image/png")

    with help_tab:
        st.markdown("""1. Start with **Try a ready-made example** to confirm the app works.
    2. Upload an image, choose **Upload audio** or **Record audio**, then click **Embed**. For recording, press the microphone, speak, and stop before embedding.
    3. Play the watermarked audio and download the ZIP.
    4. In **Decode**, upload that ZIP and click **Decode**. Compare the recovered image with the preview.

    Files are limited to **24 MB** each, including the finished output. Audio is limited to **3 minutes** and converted to **mono, 16 kHz**. Images are limited to **16 megapixels**. Full quality preserves the full resolution and decoded 8-bit RGBA image pixels in a lossless PNG attachment inside the WAV. It never shrinks the image; if the complete output is too large, it shows an error. Animated and multipage images use the first frame/page. JPEG becomes PNG without adding another JPEG compression step; original file bytes and 16-bit/HDR fidelity are not promised.

    Recordings need browser microphone permission and HTTPS (or localhost). After you stop, the recording is uploaded to this app for processing. Switching back to **Upload audio** selects an uploaded file instead of a recording. To share a personal message in one picture, choose **Audio in Image**, record, embed and send the downloaded PNG as an original file/document; the recipient can recover and listen using this website's Decode tab.

    Use the downloaded **WAV unchanged**. Conversion or editing can strip its attachment. Full-quality WAVs decode without a reference; ZIPs and earlier DSP WAV/reference pairs also work. The ZIP contains no separate image file. DSP watermark mode remains under Advanced options and may resize images substantially to fit its 8-KB capacity.

    Full quality uses file embedding, not audio-sample watermarking. Neither method encrypts images or establishes secure communication. Hosting instructions are in `docs/HOSTING.md`; the detailed DSP experiments are available below in **Advanced options**.
    """)


def render_audio_in_image():
    embed_tab, decode_tab, help_tab = st.tabs(["Embed", "Decode", "Help"])
    with embed_tab:
        st.write("Add a picture and audio, then click Embed. Download one PNG containing the hidden audio.")
        image = st.file_uploader("Cover image", key="cover_upload", help="PNG, JPEG, WebP, BMP, TIFF, GIF, ICO or AVIF. Up to 16 megapixels; first frame/page only.")
        audio = audio_source("audio_in_image", "hidden_audio_upload")
        experimental = st.session_state.get("audio_image_storage", "Full quality") == "Pixel steganography"
        st.caption("Experimental pixel mode may resize the cover to hold the audio." if experimental else
                   "Full quality: original image resolution and pixels stay unchanged. Audio is attached inside the PNG file and compressed with Opus (48 kbps by default).")
        submit = st.button("Embed", type="primary", disabled=image is None or audio is None)
        demo = st.button("Try a ready-made example")
        if submit or demo:
            try:
                with st.spinner("Preparing files, embedding audio and checking the saved PNG…"):
                    a, i = demo_inputs() if demo else (audio.getvalue(), image.getvalue())
                    if experimental:
                        result = create_audio_image(a, i, bitrate=st.session_state.get("audio_image_bitrate", 48),
                            allow_resize=st.session_state.get("audio_image_resize", True))
                    else:
                        result = create_full_audio_image(a, i, bitrate=st.session_state.get("audio_image_bitrate", 48))
                    st.session_state["audio_image_run"] = result
            except ValueError as exc:
                st.error(str(exc))
        if "audio_image_run" in st.session_state:
            run = st.session_state["audio_image_run"]
            info = run["image_info"]
            st.subheader("Last completed embedding")
            st.success("Verified: the audio recovered from the saved PNG matches exactly.")
            st.image(run["image"], caption=f"Audio-containing PNG: {info['embedded_size'][0]} × {info['embedded_size'][1]} pixels", width="stretch")
            if run.get("storage") == "file attachment":
                st.info("Original resolution and image pixels preserved exactly. Audio is attached inside the PNG; this is file embedding, not pixel steganography.")
            if info["resized"]:
                st.info(f"Resized from {info['original_size'][0]} × {info['original_size'][1]} pixels to hold the audio. Keep the downloaded PNG unchanged.")
            if info["first_frame_only"]:
                st.info("Only the first frame/page of the cover image was used.")
            st.write("Hidden audio preview")
            st.audio(run["playback_wav"], format="audio/wav")
            st.download_button("Download image with hidden audio", run["image"], "audio-in-image.png", "image/png", type="primary")

    with decode_tab:
        st.write("Upload the PNG downloaded from Audio in Image, then click Decode. No reference file is needed.")
        marked = st.file_uploader("Image with hidden audio", type=["png"], key="audio_image_decode_upload")
        if st.button("Decode", type="primary", disabled=marked is None):
            try:
                with st.spinner("Recovering and checking the hidden audio…"):
                    st.session_state["audio_image_decoded"] = decode_audio_image(marked.getvalue())
            except ValueError as exc:
                st.error(str(exc))
        if "audio_image_decoded" in st.session_state:
            result = st.session_state["audio_image_decoded"]
            st.subheader("Last completed decode")
            st.success("Audio recovered and verified.")
            st.audio(result["playback_wav"], format="audio/wav")
            st.download_button("Download recovered audio", result["audio"], "recovered.ogg", "audio/ogg")
            st.download_button("Download playable WAV", result["playback_wav"], "recovered.wav", "audio/wav")

    with help_tab:
        st.markdown("""1. Choose **Audio in Image**, add a cover, and choose **Upload audio** or **Record audio**. For a personal message, press the microphone, speak, stop and click **Embed**.
2. Download **image with hidden audio**. Full quality attaches the audio inside the PNG without changing its image pixels.
3. Open **Decode**, upload that PNG and click **Decode** to listen and download the recovered audio.

Keep the **downloaded PNG unchanged**. Screenshots, resizing, JPEG conversion, colour adjustments and messaging services that compress pictures can destroy the audio. Send it as an original file/document.

Share the downloaded PNG and this website link. The recipient selects **Audio in Image → Decode**, uploads your PNG, and listens. Recording needs browser microphone permission and HTTPS (or localhost). Once stopped, the recording is uploaded to this app for processing. If the microphone is unavailable, use Upload audio to add a recording made on your phone or computer.

Audio is limited to **3 minutes / 24 MB** and converted to **mono 16 kHz** before lossy Opus compression. Its compressed bytes recover exactly; this does not preserve the original song's file bytes or full fidelity. Covers accept the same supported image formats as Image in Audio, up to **16 megapixels**. Full quality preserves original resolution and decoded 8-bit RGBA pixels, including transparency, and uses the first frame/page. It never resizes or edits pixels. The finished PNG must fit within 24 MB. Original file bytes and 16-bit/HDR fidelity are not promised. Experimental Pixel steganography can resize to its 5-megapixel carrier limit.

Full quality is file embedding with a corruption check, not encryption or pixel steganography. Anyone with the app can recover the audio. Experimental pixel steganography remains in Advanced options and can resize the cover. Both new and earlier downloaded PNGs decode here.
""")


if mode == "Image in Audio":
    render_image_in_audio()
else:
    render_audio_in_image()

with st.expander("Advanced options", expanded=False):
    st.caption("Automatic modes work without these controls. The earlier DSP lab is preserved here; its settings apply to the advanced experiment, separately from the automatic modes.")
    st.subheader("Embedding method")
    st.selectbox("Image in Audio method", ["Full quality", "DSP watermark"], key="image_storage",
                 help="Full quality preserves the image resolution/pixels using a WAV attachment. DSP watermark is experimental and can shrink the image substantially.")
    st.selectbox("Audio in Image method", ["Full quality", "Pixel steganography"], key="audio_image_storage",
                 help="Full quality preserves image pixels using a PNG attachment. Pixel steganography edits RGB low bits and may resize the cover.")
    st.subheader("Audio in Image settings")
    st.selectbox("Audio quality (kbps)", [32, 48, 64], index=1, key="audio_image_bitrate",
                 help="Higher bitrate increases the hidden audio size and may require a larger picture.")
    st.checkbox("Resize image automatically", value=True, key="audio_image_resize", help="Applies only to experimental Pixel steganography. Full quality never resizes.")
    if "audio_image_run" in st.session_state:
        run = st.session_state["audio_image_run"]
        st.json({"image": run["image_info"], "audio": run["audio_info"]})
    st.divider()
    from advanced import render_advanced_lab
    render_advanced_lab()
