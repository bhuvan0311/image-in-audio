"""Self-contained audio in PNG pixels, with bounded conversion and verified recovery.

Container v1: RGB least-significant bits, row-major, big bit order; an 8-byte
magic, unsigned little-endian byte length and SHA-256 precede Ogg Opus bytes.
Alpha is never used. The hash detects corruption, not malicious replacement.
"""
from __future__ import annotations
import hashlib
import io
import math
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from .engine import wav_bytes
from .media import bounded, png_bytes, prepare_audio, MAX_PIXELS

MAGIC = b"AWIMG001"
HEADER = struct.Struct("<8sI32s")
MAX_AUDIO_BYTES = 2_000_000
MAX_CARRIER_PIXELS = 5_000_000
MAX_SIDE = 8192


def _image(data, *, carrier=False):
    bounded(data)
    try:
        with Image.open(io.BytesIO(data)) as source:
            limit = MAX_CARRIER_PIXELS if carrier else MAX_PIXELS
            if source.width * source.height > limit:
                raise ValueError(f"Image exceeds the {limit // 1_000_000} megapixel limit.")
            if carrier and (source.format != "PNG" or source.mode not in {"RGB", "RGBA"}):
                raise ValueError("Upload the unchanged RGB/RGBA PNG downloaded from Audio in Image.")
            first_frame = getattr(source, "n_frames", 1) > 1
            # Do not reorient a marked image: embedded bit order follows saved pixels.
            im = (source if carrier else ImageOps.exif_transpose(source)).convert("RGBA")
            im.load()
            return im, first_frame
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Cannot read this image. Use a supported image, or the downloaded PNG for decoding.") from exc


def _opus(audio_data, bitrate):
    if type(bitrate) is not int or bitrate not in {32, 48, 64}:
        raise ValueError("Choose an audio bitrate of 32, 48 or 64 kbps.")
    fs, x, info = prepare_audio(audio_data)
    ffmpeg = shutil.which("ffmpeg")
    with tempfile.TemporaryDirectory(prefix="audio-image-") as scratch:
        src, dst = Path(scratch)/"prepared.wav", Path(scratch)/"payload.ogg"
        src.write_bytes(wav_bytes(x, fs, bits=24))
        try:
            proc = subprocess.run([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
                "-protocol_whitelist", "file,pipe", "-format_whitelist", "wav",
                "-i", str(src), "-map", "0:a:0", "-map_metadata", "-1", "-vn",
                "-c:a", "libopus", "-b:a", f"{bitrate}k", "-vbr", "off",
                "-application", "audio", "-y", str(dst)], capture_output=True, timeout=45,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError("Audio compression failed or timed out. Try a smaller file.") from exc
        if proc.returncode or not dst.exists():
            raise ValueError("Audio compression needs FFmpeg with the libopus encoder.")
        payload = dst.read_bytes()
    if not 1 <= len(payload) <= MAX_AUDIO_BYTES:
        raise ValueError("Compressed audio exceeds image capacity. Use shorter audio.")
    info.update({"codec": "Opus", "container": "Ogg", "bitrate_kbps": bitrate,
                 "lossy_compression": True, "byte_length": len(payload),
                 "sha256": hashlib.sha256(payload).hexdigest()})
    return payload, info


def _carrier_size(size, required_pixels, allow_resize):
    width, height = size
    if not allow_resize:
        if width * height > MAX_CARRIER_PIXELS:
            raise ValueError("Carrier exceeds 5 megapixels. Enable automatic image resizing.")
        if width * height < required_pixels:
            raise ValueError("Image is too small for this audio. Enable automatic resizing or use a larger image/shorter audio.")
        return size
    # Bound extreme aspect ratios to keep dimension and memory limits predictable.
    ratio = min(64., max(1/64., width / height))
    target = min(MAX_CARRIER_PIXELS - MAX_SIDE, max(required_pixels, width * height))
    new_width = max(1, min(MAX_SIDE, math.ceil(math.sqrt(target * ratio))))
    new_height = max(1, math.ceil(target / new_width))
    if size[0] * size[1] <= MAX_CARRIER_PIXELS and max(size) <= MAX_SIDE and size[0] * size[1] >= required_pixels:
        return size
    if new_width * new_height > MAX_CARRIER_PIXELS or new_height > MAX_SIDE or new_width * new_height < required_pixels:
        raise ValueError("Audio cannot fit within the image size limit. Use shorter audio.")
    return new_width, new_height


def extract_audio_bytes(image_data):
    """Read a validated Opus payload without an original image or reference file."""
    from .full_quality import extract_full_audio
    attached = extract_full_audio(image_data)
    if attached is not None:
        return attached
    im, _ = _image(image_data, carrier=True)
    rgb = np.asarray(im, dtype=np.uint8)[..., :3].copy().reshape(-1)
    if rgb.size < HEADER.size * 8:
        raise ValueError("This PNG is too small to contain hidden audio.")
    header = np.packbits(rgb[:HEADER.size * 8] & 1).tobytes()
    magic, length, digest = HEADER.unpack(header)
    if magic != MAGIC:
        raise ValueError("No supported hidden audio found. Use the PNG downloaded from Audio in Image.")
    if not 1 <= length <= MAX_AUDIO_BYTES or (HEADER.size + length) * 8 > rgb.size:
        raise ValueError("Invalid or damaged hidden-audio length.")
    payload = np.packbits(rgb[HEADER.size * 8:(HEADER.size + length) * 8] & 1).tobytes()
    if hashlib.sha256(payload).digest() != digest:
        raise ValueError("Audio verification failed. Use the unchanged downloaded PNG; resizing or image compression can damage the hidden audio.")
    if not payload.startswith(b"OggS") or b"OpusHead" not in payload[:100]:
        raise ValueError("Unsupported hidden audio encoding.")
    return payload


def decode_audio_image(image_data):
    payload = extract_audio_bytes(image_data)
    # Decode before success/playback: a valid hash alone does not establish playable audio.
    fs, x, info = prepare_audio(payload)
    return {"audio": payload, "playback_wav": wav_bytes(x, fs, bits=24),
            "verified": True, "audio_info": info,
            "audio_sha256": hashlib.sha256(payload).hexdigest()}


def create_audio_image(audio_data, image_data, *, bitrate=48, allow_resize=True):
    im, first_frame = _image(image_data)
    original_size = im.size
    payload, audio_info = _opus(audio_data, bitrate)
    packet = HEADER.pack(MAGIC, len(payload), hashlib.sha256(payload).digest()) + payload
    size = _carrier_size(im.size, math.ceil(len(packet) * 8 / 3), allow_resize)
    if size != im.size:
        im = im.resize(size, Image.Resampling.LANCZOS)
    original = np.asarray(im, dtype=np.uint8)
    rgb = original[..., :3].copy().reshape(-1)
    bits = np.unpackbits(np.frombuffer(packet, dtype=np.uint8))
    rgb[:bits.size] = (rgb[:bits.size] & 254) | bits
    pixels = original.copy()
    pixels[..., :3] = rgb.reshape(pixels.shape[0], pixels.shape[1], 3)
    saved = png_bytes(Image.fromarray(pixels))
    bounded(saved)
    decoded = decode_audio_image(saved)
    if decoded["audio"] != payload:
        raise ValueError("Saved image failed audio verification; no download was produced.")
    image_info = {"original_size": list(original_size), "embedded_size": list(size),
                  "resized": size != original_size, "first_frame_only": first_frame,
                  "capacity_bytes": rgb.size // 8 - HEADER.size,
                  "max_rgb_change": int(np.abs(pixels[..., :3].astype(np.int16) - original[..., :3]).max()),
                  "alpha_preserved": bool(np.array_equal(pixels[..., 3], original[..., 3])),
                  "format": "PNG", "mode": "RGBA", "payload_bytes": len(payload)}
    return {"image": saved, "audio": payload, "playback_wav": decoded["playback_wav"],
            "audio_info": audio_info, "image_info": image_info, "verified": True}
