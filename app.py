"""Two automatic media-hiding modes with the complete advanced DSP lab."""
import streamlit as st
from watermark_lab.media import create_image_audio, decode_image_audio, download_bundle, read_bundle, demo_inputs
from watermark_lab.audio_image import create_audio_image, decode_audio_image

st.set_page_config(page_title="Image & Audio Lab", page_icon="🎵", layout="centered")
st.title("Image & Audio Lab")
st.write("Hide an image in audio, or audio in an image. Embed, download and recover in a few clicks.")
mode = st.radio("What would you like to hide?", ["Image in Audio", "Audio in Image"], horizontal=True, key="hiding_mode")


def render_image_in_audio():
    embed_tab, decode_tab, help_tab = st.tabs(["Embed", "Decode", "Help"])

    with embed_tab:
        st.write("Add your image and audio, then click Embed. The app chooses the settings and checks the saved result.")
        image = st.file_uploader("Image", key="image_upload", help="PNG, JPEG, WebP, BMP, TIFF, GIF, ICO and AVIF. First frame/page only. Maximum 16 megapixels.")
        audio = st.file_uploader("Audio or song", key="simple_audio_upload", help="WAV, MP3, FLAC, M4A, AAC, OGG, Opus, AIFF and WMA. Maximum 24 MB and 3 minutes; no DRM.")
        st.caption("Audio becomes mono, 16 kHz WAV. Large images are resized to fit; the embedded size is shown. Colour and transparency are preserved in the prepared image.")
        submit = st.button("Embed", type="primary", disabled=image is None or audio is None)
        demo = st.button("Try a ready-made example")
        if submit or demo:
            try:
                with st.spinner("Preparing files, embedding and checking the downloaded audio…"):
                    a, i = demo_inputs() if demo else (audio.getvalue(), image.getvalue())
                    result = create_image_audio(a, i)
                    result["bundle"] = download_bundle(result)
                    st.session_state["image_run"] = result
            except ValueError as exc:
                st.error(str(exc))
        if "image_run" in st.session_state:
            run = st.session_state["image_run"]
            info = run["image_info"]
            st.subheader("Last completed embedding")
            st.success("Verified: the image recovered from the saved audio matches exactly.")
            st.image(run["image"], caption=f"Image embedded: {info['embedded_size'][0]} × {info['embedded_size'][1]} pixels", width=256)
            if info["resized"]:
                st.info(f"Resized from {info['original_size'][0]} × {info['original_size'][1]} to fit the audio. Recovery is exact for the image shown here.")
            if info["first_frame_only"]:
                st.info("Only the first frame/page of the uploaded image was embedded.")
            st.write("Watermarked audio")
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
        st.write("Upload the ZIP downloaded after Embed, then click Decode.")
        bundle = st.file_uploader("Audio + reference ZIP", type=["zip"], key="bundle_upload")
        with st.expander("Use separate WAV and reference files"):
            marked = st.file_uploader("Watermarked WAV", type=["wav"], key="marked_upload")
            reference = st.file_uploader("Reference JSON", type=["json"], key="reference_upload")
        st.caption("Keep the matching reference. This method needs it to recover the image; it is not an encryption key.")
        if st.button("Decode", type="primary", disabled=bundle is None and (marked is None or reference is None)):
            try:
                with st.spinner("Recovering and verifying image…"):
                    a, r = read_bundle(bundle.getvalue()) if bundle is not None else (marked.getvalue(), reference.getvalue())
                    st.session_state["image_decoded"] = decode_image_audio(a, r)
            except ValueError as exc:
                st.error(str(exc))
        if "image_decoded" in st.session_state:
            recovered = st.session_state["image_decoded"]
            st.subheader("Last completed decode")
            st.success("Image recovered and verified.")
            st.image(recovered["image"], caption="Recovered image", width=256)
            st.audio(recovered["audio"], format="audio/wav")
            st.download_button("Download recovered image", recovered["image"], "recovered.png", "image/png")

    with help_tab:
        st.markdown("""1. Start with **Try a ready-made example** to confirm the app works.
    2. Upload an image and a song, then click **Embed**.
    3. Play the watermarked audio and download the ZIP.
    4. In **Decode**, upload that ZIP and click **Decode**. Compare the recovered image with the preview.

    Files are limited to **24 MB** each. Audio is limited to **3 minutes** and converted to **mono, 16 kHz**. Images are limited to **16 megapixels**; the app embeds a lossless PNG representation, resizing if needed to fit up to 8 KB of payload. Animated and multipage images use the first frame/page. Support depends on the installed image and audio codecs; unsupported or DRM-protected files show an error.

    Use the downloaded **WAV unchanged**. MP3 conversion, cropping, volume changes and other edits can damage the image. An invalid recovery shows an error instead of an unverified image. The reference contains original transform coefficients and image metadata; the ZIP does not contain the image itself.

    This app demonstrates reference-dependent watermarking. It does not encrypt images or prove inaudibility, resistance to attacks, or secure communication. Hosting instructions are in `docs/HOSTING.md`; the detailed DSP experiments are available below in **Advanced options**.
    """)


def render_audio_in_image():
    embed_tab, decode_tab, help_tab = st.tabs(["Embed", "Decode", "Help"])
    with embed_tab:
        st.write("Add a picture and audio, then click Embed. Download one PNG containing the hidden audio.")
        image = st.file_uploader("Cover image", key="cover_upload", help="PNG, JPEG, WebP, BMP, TIFF, GIF, ICO or AVIF. Up to 16 megapixels; first frame/page only.")
        audio = st.file_uploader("Audio or song", key="hidden_audio_upload", help="WAV, MP3, FLAC, M4A, AAC, OGG, Opus, AIFF or WMA. Up to 24 MB and 3 minutes.")
        st.caption("Audio is converted to mono 16 kHz and compressed with Opus (48 kbps by default). The picture is resized when needed, up to 5 megapixels. Recovery is exact for the compressed audio, not the original file.")
        submit = st.button("Embed", type="primary", disabled=image is None or audio is None)
        demo = st.button("Try a ready-made example")
        if submit or demo:
            try:
                with st.spinner("Preparing files, embedding audio and checking the saved PNG…"):
                    a, i = demo_inputs() if demo else (audio.getvalue(), image.getvalue())
                    st.session_state["audio_image_run"] = create_audio_image(a, i,
                        bitrate=st.session_state.get("audio_image_bitrate", 48),
                        allow_resize=st.session_state.get("audio_image_resize", True))
            except ValueError as exc:
                st.error(str(exc))
        if "audio_image_run" in st.session_state:
            run = st.session_state["audio_image_run"]
            info = run["image_info"]
            st.subheader("Last completed embedding")
            st.success("Verified: the audio recovered from the saved PNG matches exactly.")
            st.image(run["image"], caption=f"Audio-containing PNG: {info['embedded_size'][0]} × {info['embedded_size'][1]} pixels", width=256)
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
        st.markdown("""1. Choose **Audio in Image**, add your files and click **Embed** (or try the ready-made example).
2. Download **image with hidden audio**. The audio is inside the PNG's pixels.
3. Open **Decode**, upload that PNG and click **Decode** to listen and download the recovered audio.

Keep the **downloaded PNG unchanged**. Screenshots, resizing, JPEG conversion, colour adjustments and messaging services that compress pictures can destroy the audio. Send it as an original file/document.

Audio is limited to **3 minutes / 24 MB** and converted to **mono 16 kHz** before lossy Opus compression. Its compressed bytes recover exactly; this does not preserve the original song's file bytes or full fidelity. Covers accept the same supported image formats as Image in Audio, up to **16 megapixels**. The output is always an 8-bit RGBA PNG, automatically resized to at most **5 megapixels**, and uses the first frame/page. Transparent pixels retain their alpha values after resizing.

This is pixel steganography with a corruption check. It is not encryption or authenticated communication. Anyone with the app can recover the audio. Advanced audio-quality and resizing controls, verification details and the earlier DSP experiments are below in **Advanced options**.
""")


if mode == "Image in Audio":
    render_image_in_audio()
else:
    render_audio_in_image()

with st.expander("Advanced options", expanded=False):
    st.caption("Automatic modes work without these controls. The earlier DSP lab is preserved here; its settings apply to the advanced experiment, separately from the automatic modes.")
    st.subheader("Audio in Image settings")
    st.selectbox("Audio quality (kbps)", [32, 48, 64], index=1, key="audio_image_bitrate",
                 help="Higher bitrate increases the hidden audio size and may require a larger picture.")
    st.checkbox("Resize image automatically", value=True, key="audio_image_resize")
    if "audio_image_run" in st.session_state:
        run = st.session_state["audio_image_run"]
        st.json({"image": run["image_info"], "audio": run["audio_info"]})
    st.divider()
    from advanced import render_advanced_lab
    render_advanced_lab()
