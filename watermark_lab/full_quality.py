"""Full-resolution file embedding in private WAV/PNG chunks, not DSP/LSB hiding.

PNG: https://www.w3.org/TR/png-3/ ; RIFF: Microsoft's RIFF specification.
The unkeyed digest detects corruption, not authenticity or confidentiality.
"""
from __future__ import annotations
import hashlib
import io
import json
import struct
import zlib

from PIL import Image, UnidentifiedImageError

from .engine import wav_bytes, MAX_FILE_BYTES
from .media import bounded, prepare_audio, png_bytes, MAX_PIXELS

SCHEMA = "image-in-wav-chunk-v1"
MAGIC = b"AWFULL01"
HEADER = struct.Struct("<8sI32s")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_CHUNK = b"auDi"
WAV_CHUNK = b"imAg"


def full_image(data):
    # Reuse bounded image decoding but give it the entire file budget. Reject
    # oversize output instead of silently discarding pixels to fit a watermark.
    from .audio_image import _image
    im, first = _image(data)
    saved = png_bytes(im)
    bounded(saved)
    return saved, {"original_size": list(im.size), "embedded_size": list(im.size),
        "resized": False, "first_frame_only": first, "byte_length": len(saved),
        "sha256": hashlib.sha256(saved).hexdigest(), "format": "PNG", "mode": "RGBA",
        "bitorder": "big", "storage": "file attachment", "pixels_preserved": True}


def _packet(data):
    return HEADER.pack(MAGIC, len(data), hashlib.sha256(data).digest()) + data


def _unpack(packet):
    if len(packet) < HEADER.size:
        raise ValueError("Incomplete embedded file header.")
    magic, length, digest = HEADER.unpack(packet[:HEADER.size])
    data = packet[HEADER.size:]
    if magic != MAGIC or not 1 <= length <= MAX_FILE_BYTES or length != len(data):
        raise ValueError("Invalid embedded file length or format.")
    if hashlib.sha256(data).digest() != digest:
        raise ValueError("Embedded file verification failed. Use the unchanged downloaded file.")
    return data


def riff_chunks(data):
    bounded(data)
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE" or struct.unpack("<I", data[4:8])[0] + 8 != len(data):
        raise ValueError("Invalid or incomplete WAV container.")
    chunks, pos = [], 12
    while pos < len(data):
        if pos + 8 > len(data):
            raise ValueError("Incomplete WAV chunk header.")
        kind, length = struct.unpack("<4sI", data[pos:pos+8])
        end = pos + 8 + length
        following = end + (length & 1)
        if following > len(data):
            raise ValueError("Invalid WAV chunk length.")
        chunks.append((kind, data[pos+8:end]))
        pos = following
    return chunks


def decode_full_image_audio(audio):
    packets = [data for kind, data in riff_chunks(audio) if kind == WAV_CHUNK]
    if len(packets) != 1:
        raise ValueError("No unique full-quality image attachment found. Older DSP files need their reference ZIP.")
    image = _unpack(packets[0])
    try:
        with Image.open(io.BytesIO(image)) as im:
            if im.format != "PNG" or im.mode != "RGBA" or im.width * im.height > MAX_PIXELS:
                raise ValueError("Invalid full-quality image attachment.")
            im.load()
            size = list(im.size)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Invalid full-quality image attachment.") from exc
    # Validate playable bounded audio before reporting success.
    from .engine import read_wav
    read_wav(audio)
    return {"image": image, "audio": audio, "verified": True,
        "image_info": {"embedded_size": size, "resized": False, "pixels_preserved": True}}


def create_full_image_audio(audio_data, image_data):
    image, info = full_image(image_data)
    fs, samples, audio_info = prepare_audio(audio_data)
    original = wav_bytes(samples, fs, bits=24)
    packet = _packet(image)
    chunk = WAV_CHUNK + struct.pack("<I", len(packet)) + packet + (b"\0" if len(packet) & 1 else b"")
    audio = original[:4] + struct.pack("<I", len(original) + len(chunk) - 8) + original[8:] + chunk
    bounded(audio)
    reference = json.dumps({"schema": SCHEMA, "image": info, "audio": audio_info}, separators=(",", ":")).encode()
    if decode_full_image_audio(audio)["image"] != image:
        raise ValueError("Saved WAV failed full-quality image verification.")
    return {"audio": audio, "reference": reference, "image": image, "image_info": info,
        "audio_info": audio_info, "original_audio": original,
        "metrics": {"ber": 0., "clipping_count": 0, "snr_db": None}, "storage": "file attachment"}


def png_chunks(data):
    bounded(data)
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("Upload the downloaded PNG.")
    chunks, pos, ended = [], 8, False
    while pos < len(data):
        if pos + 12 > len(data):
            raise ValueError("Incomplete PNG chunk header.")
        length = struct.unpack(">I", data[pos:pos+4])[0]
        kind = data[pos+4:pos+8]
        end = pos + 8 + length
        if end + 4 > len(data):
            raise ValueError("Invalid PNG chunk length.")
        body = data[pos+8:end]
        crc = struct.unpack(">I", data[end:end+4])[0]
        if zlib.crc32(kind + body) & 0xffffffff != crc:
            raise ValueError("PNG verification failed. Use the unchanged downloaded file.")
        chunks.append((kind, body, pos, end+4))
        pos = end + 4
        if kind == b"IEND":
            if length or pos != len(data):
                raise ValueError("Invalid PNG ending.")
            ended = True
            break
    if not ended or not chunks or chunks[0][0] != b"IHDR":
        raise ValueError("Invalid PNG structure.")
    return chunks


def extract_full_audio(image):
    packets = [body for kind, body, _, _ in png_chunks(image) if kind == PNG_CHUNK]
    if not packets:
        return None  # Permit existing RGB-LSB PNGs in the shared decoder.
    if len(packets) != 1:
        raise ValueError("Duplicate embedded audio attachments.")
    from .audio_image import _image, MAX_AUDIO_BYTES
    _image(image)  # Full-resolution dimensions/mode validated by Pillow.
    payload = _unpack(packets[0])
    if len(payload) > MAX_AUDIO_BYTES or not payload.startswith(b"OggS") or b"OpusHead" not in payload[:100]:
        raise ValueError("Unsupported embedded audio encoding.")
    return payload


def create_full_audio_image(audio_data, image_data, *, bitrate=48):
    from .audio_image import _opus, decode_audio_image
    image, info = full_image(image_data)
    payload, audio_info = _opus(audio_data, bitrate)
    packet = _packet(payload)
    chunk = struct.pack(">I", len(packet)) + PNG_CHUNK + packet + struct.pack(">I", zlib.crc32(PNG_CHUNK + packet) & 0xffffffff)
    ending = png_chunks(image)[-1][2]
    saved = image[:ending] + chunk + image[ending:]
    bounded(saved)
    decoded = decode_audio_image(saved)
    if decoded["audio"] != payload:
        raise ValueError("Saved PNG failed audio verification.")
    # Chunk embedding keeps encoded image data untouched, hence pixel equality.
    info.update({"payload_bytes": len(payload), "max_rgb_change": 0, "alpha_preserved": True})
    return {"image": saved, "audio": payload, "playback_wav": decoded["playback_wav"],
        "image_info": info, "audio_info": audio_info, "verified": True, "storage": "file attachment"}
