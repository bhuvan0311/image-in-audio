"""Bounded upload conversion and verified image-in-audio workflow."""
from __future__ import annotations
import hashlib
import io
import json
import shutil
import subprocess
import tempfile
import warnings
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from scipy.io import wavfile
from .engine import MAX_FILE_BYTES, MAX_SAMPLES, capacity, embed, extract, read_wav, wav_bytes, validate_reference, evaluate, generate_audio

FS = 16000
MAX_PAYLOAD_BYTES = 8192
MAX_PIXELS = 16_000_000
SCHEMA = "image-in-audio-v1"


def bounded(data):
    if not data or len(data) > MAX_FILE_BYTES:
        raise ValueError("Use a nonempty file smaller than 24 MB.")


def png_bytes(im):
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def prepare_image(data, budget):
    bounded(data)
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.width * source.height > MAX_PIXELS:
                raise ValueError("Image exceeds the 16 megapixel limit.")
            animated = getattr(source, "n_frames", 1) > 1
            im = ImageOps.exif_transpose(source).convert("RGBA")
            original_size = im.size
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Cannot read this image. Try PNG, JPEG, WebP, BMP, TIFF, GIF, ICO or AVIF.") from exc
    budget = min(int(budget), MAX_PAYLOAD_BYTES)
    data = png_bytes(im)
    while len(data) > budget and max(im.size) > 1:
        width, height = im.size
        im = im.resize((max(1, int(width * .8)), max(1, int(height * .8))), Image.Resampling.LANCZOS)
        data = png_bytes(im)
    if len(data) > budget:
        raise ValueError("Audio is too short to hold an image. Use a longer recording.")
    return data, {"original_size": list(original_size), "embedded_size": list(im.size),
                  "resized": original_size != im.size, "first_frame_only": animated,
                  "byte_length": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                  "format": "PNG", "mode": "RGBA", "bitorder": "big"}


def prepare_audio(data):
    bounded(data)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValueError("Audio conversion needs FFmpeg. Install it or use the supplied hosting configuration.")
    with tempfile.TemporaryDirectory(prefix="watermark-") as scratch:
        src, dst = Path(scratch)/"upload.bin", Path(scratch)/"converted.wav"
        src.write_bytes(data)
        try:
            proc = subprocess.run([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
                "-protocol_whitelist", "file,pipe", "-format_whitelist", "wav,mp3,flac,mov,aac,ogg,aiff,asf",
                "-i", str(src), "-map", "0:a:0", "-vn",
                "-ac", "1", "-ar", str(FS), "-t", "180.001", "-c:a", "pcm_f32le", "-y", str(dst)],
                capture_output=True, timeout=45, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired as exc:
            raise ValueError("Audio conversion timed out. Try a smaller file.") from exc
        if proc.returncode or not dst.exists():
            raise ValueError("Cannot decode this audio. Try WAV, MP3, FLAC, M4A, AAC, OGG, Opus, AIFF or WMA without DRM.")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", wavfile.WavFileWarning)
            fs, raw = wavfile.read(dst)
    x = np.asarray(raw, dtype=float)
    if x.ndim != 1 or not 16 <= x.size <= MAX_SAMPLES:
        raise ValueError("Use audio between 0.001 and 180 seconds long. Longer songs must be shortened before upload.")
    if not np.all(np.isfinite(x)):
        raise ValueError("Audio contains invalid samples.")
    pad = (-len(x)) % 4
    x = np.pad(x, (0, pad))
    peak = float(np.max(np.abs(x)))
    gain = min(1., .65 / peak) if peak else 1.
    return fs, x * gain, {"sample_rate": fs, "channels": 1, "duration_seconds": len(x)/fs,
                           "input_gain": gain, "padding_samples": pad}


def create_image_audio(audio_data, image_data):
    fs, x, audio_info = prepare_audio(audio_data)
    image, image_info = prepare_image(image_data, capacity(len(x)) // 8)
    bits = np.unpackbits(np.frombuffer(image, dtype=np.uint8))
    # PCM24 projection bound at maximum supported N is < .000102; alpha=.02.
    for _ in range(6):
        try:
            result = embed(x, fs, bits, strength=.02)
            break
        except ValueError as exc:
            if "Output lacks" not in str(exc):
                raise
            x = x * .8
            audio_info["input_gain"] *= .8
    else:
        raise ValueError("Cannot supply enough audio headroom for this image.")
    audio = wav_bytes(result.audio, fs, bits=24)
    ref = {"schema": SCHEMA, "dsp": result.reference, "image": image_info, "audio": audio_info}
    ref_data = json.dumps(ref, separators=(",", ":"), allow_nan=False).encode()
    recovered = decode_image_audio(audio, ref_data)
    if recovered["image"] != image:
        raise ValueError("Saved audio failed image verification; no download was produced.")
    fs, saved = read_wav(audio)
    rb, scores = extract(saved, fs, result.reference)
    metrics = evaluate(x, saved, bits, rb, scores)
    return {"audio": audio, "reference": ref_data, "image": image, "image_info": image_info,
            "audio_info": audio_info, "metrics": metrics, "original_audio": wav_bytes(x, fs, bits=24)}


def decode_image_audio(audio, reference):
    bounded(audio)
    bounded(reference)
    try:
        ref = json.loads(reference)
        if isinstance(ref, dict) and ref.get("schema") == "image-in-wav-chunk-v1":
            from .full_quality import decode_full_image_audio
            result = decode_full_image_audio(audio)
            if hashlib.sha256(result["image"]).hexdigest() != ref["image"]["sha256"]:
                raise ValueError("Image verification failed. Use the matching WAV and reference.")
            return result
        if not isinstance(ref, dict) or ref.get("schema") != SCHEMA:
            raise ValueError("Use the reference downloaded from the image app.")
        validate_reference(ref["dsp"])
        info = ref["image"]
        length = info["byte_length"]
        if type(length) is not int or not 1 <= length <= MAX_PAYLOAD_BYTES or ref["dsp"]["payload_length"] != length * 8:
            raise ValueError("Invalid image payload length.")
        if (info["format"], info["mode"], info["bitorder"]) != ("PNG", "RGBA", "big"):
            raise ValueError("Unsupported image encoding.")
        fs, x = read_wav(audio)
        bits, _ = extract(x, fs, ref["dsp"])
        png = np.packbits(bits).tobytes()
        if hashlib.sha256(png).hexdigest() != info["sha256"]:
            raise ValueError("Image verification failed. Use the matching reference and unchanged downloaded WAV; compression or editing can damage the hidden image.")
        with Image.open(io.BytesIO(png)) as im:
            if im.format != "PNG" or im.width * im.height > MAX_PIXELS:
                raise ValueError("Invalid recovered image.")
            im.load()
        return {"image": png, "audio": audio, "image_info": info, "verified": True}
    except (KeyError, TypeError, UnicodeError, json.JSONDecodeError, OSError) as exc:
        raise ValueError("Invalid reference or recovered image.") from exc


def download_bundle(run):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("watermarked.wav", run["audio"])
        archive.writestr("reference.json", run["reference"])
        attachment = run.get("storage") == "file attachment"
        archive.writestr("README.txt", "Upload this ZIP in Decode to recover the image and play the audio. Keep the WAV unchanged. " +
            ("The full-resolution image is a private attachment inside the WAV container, not a DSP watermark. The WAV also decodes alone. " if attachment else
             "The matching reference is required and is not an encryption key. The image is embedded in the audio samples. ") +
            "This ZIP does not contain an image sidecar. Neither method encrypts the image.\n")
    return buf.getvalue()


def read_bundle(data):
    bounded(data)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 3 or len({e.filename for e in entries}) != len(entries):
                raise ValueError("Invalid bundle contents.")
            if any(e.filename not in {"watermarked.wav", "reference.json", "README.txt"} or e.file_size > MAX_FILE_BYTES for e in entries):
                raise ValueError("Bundle contains unexpected files or exceeds size limits.")
            return archive.read("watermarked.wav"), archive.read("reference.json")
    except (zipfile.BadZipFile, KeyError, RuntimeError, NotImplementedError) as exc:
        raise ValueError("Cannot read this bundle. Upload the ZIP downloaded after Embed.") from exc


def demo_inputs():
    im = Image.new("RGBA", (24, 24))
    im.putdata([(r*10, c*10, (r+c)*5, 255) for r in range(24) for c in range(24)])
    return wav_bytes(generate_audio(seconds=8), FS), png_bytes(im)
