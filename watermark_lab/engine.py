"""Coherent signed FFT displacement in a Haar subband. No blind detector."""
from __future__ import annotations
import io
import json
import time
import wave
from dataclasses import dataclass

import numpy as np
import pywt
from PIL import Image
from scipy.io import wavfile

MAX_SAMPLES = 2_880_000
MAX_FILE_BYTES = 24_000_000
SCHEMA = "haar-fft-reference-v1"


def audio_array(x):
    raw = np.asarray(x)
    if np.iscomplexobj(raw):
        raise ValueError("Audio must be real.")
    x = np.asarray(raw, dtype=np.float64)
    if x.ndim != 1 or not 16 <= x.size <= MAX_SAMPLES:
        raise ValueError(f"Mono audio must contain 16–{MAX_SAMPLES:,} samples.")
    if not np.all(np.isfinite(x)):
        raise ValueError("Audio contains non-finite samples.")
    if np.max(np.abs(x)) >= 1:
        raise ValueError("Audio must have peak below 1. Supply headroom before embedding.")
    return x


def sample_rate(fs):
    if isinstance(fs, bool) or int(fs) != fs or not 8000 <= fs <= 96000:
        raise ValueError("Sample rate must be an integer between 8,000 and 96,000 Hz.")
    return int(fs)


def payload_bits(bits, allow_empty=False):
    bits = np.asarray(bits)
    if bits.ndim != 1 or (not allow_empty and not bits.size) or bits.size > MAX_SAMPLES:
        raise ValueError("Payload must be a nonempty one-dimensional bit vector.")
    if not np.all((bits == 0) | (bits == 1)):
        raise ValueError("Payload contains values other than 0 and 1.")
    return bits.astype(np.uint8)


def band_index(level, band):
    if isinstance(level, bool) or not isinstance(level, (int, np.integer)) or level not in (1, 2, 3, 4):
        raise ValueError("Haar level must be 1, 2, 3, or 4.")
    if band == f"A{level}":
        return 0
    if band in [f"D{j}" for j in range(1, level + 1)]:
        return level - int(band[1:]) + 1
    raise ValueError("Subband is incompatible with the decomposition level.")


def decompose(x, level):
    n = len(x)
    padded = ((n + 2**level - 1) // 2**level) * 2**level
    return pywt.wavedec(np.pad(x, (0, padded - n)), "haar", mode="periodization", level=level), padded


def capacity(n, level=2, band="A2"):
    idx = band_index(level, band)
    padded = ((n + 2**level - 1) // 2**level) * 2**level
    m = padded // 2**(level if idx == 0 else int(band[1:]))
    return (m - 1) // 2  # excludes DC and (when even) Nyquist


@dataclass
class Embedding:
    audio: np.ndarray
    reference: dict
    seconds: float


def embed(x, fs, bits, strength=0.06, level=2, band="A2", block_size=None):
    start = time.perf_counter()
    x = audio_array(x)
    fs = sample_rate(fs)
    if np.max(np.abs(x)) >= 1 - 1 / 32768:
        raise ValueError("Input lacks PCM16 headroom. Reduce input gain before embedding.")
    bits = payload_bits(bits, allow_empty=True)
    idx = band_index(level, band)
    if not np.isfinite(strength) or not 0.001 <= strength <= 0.5:
        raise ValueError("Strength must be finite and between 0.001 and 0.5.")
    if block_size is not None and (isinstance(block_size, bool) or int(block_size) != block_size or block_size < 64 or block_size > MAX_SAMPLES or block_size % 2**level):
        raise ValueError("Block size must be an integer ≥64, divisible by 2^level.")
    step = int(block_size) if block_size is not None else len(x)
    spans = [(s, min(s + step, len(x))) for s in range(0, len(x), step)]
    total_cap = sum(capacity(e - s, level, band) for s, e in spans)
    if len(bits) > total_cap:
        raise ValueError(f"Payload has {len(bits)} bits; available capacity is {total_cap} bits.")
    out = np.empty_like(x)
    records = []
    offset = 0
    for s, e in spans:
        t0 = time.perf_counter()
        coeffs, padded = decompose(x[s:e], level)
        m = len(coeffs[idx])
        take = min(len(bits) - offset, capacity(e - s, level, band))
        bins = np.arange(1, take + 1)
        spectrum = np.fft.rfft(coeffs[idx], norm="ortho")
        original = spectrum[bins].copy()
        # Canonicalize signed complex zero; JSON reconstruction can lose its sign.
        direction = np.where(np.abs(original) == 0, 1 + 0j, np.exp(1j * np.angle(original)))
        spectrum[bins] += strength * (2 * bits[offset:offset + take].astype(float) - 1) * direction
        coeffs[idx] = np.fft.irfft(spectrum, n=m, norm="ortho")
        out[s:e] = pywt.waverec(coeffs, "haar", mode="periodization")[:e-s]
        # Simultaneously live algorithm arrays; excludes Python/FFT-library overhead.
        buffer_bytes = int(2 * padded * 8 + sum(c.nbytes for c in coeffs) + spectrum.nbytes + original.nbytes + direction.nbytes + bins.nbytes)
        records.append({"start": s, "end": e, "padded": padded, "band_length": m,
                        "count": take, "original_real": original.real.tolist(),
                        "original_imag": original.imag.tolist(), "seconds": time.perf_counter()-t0,
                        "estimated_array_bytes": buffer_bytes})
        offset += take
    if not np.all(np.isfinite(out)) or np.max(np.abs(out)) >= 1 - 1 / 32768:
        raise ValueError("Output lacks PCM16 headroom. Reduce input level or embedding strength; no automatic normalization is applied.")
    reference = {"schema": SCHEMA, "sample_rate": fs, "samples": len(x), "level": level,
                 "band": band, "strength": float(strength), "payload_length": len(bits),
                 "capacity_bits": total_cap, "block_size": block_size, "blocks": records,
                 "wavelet": "haar", "mode": "periodization", "fft_norm": "ortho",
                 "padding": "zero at end of each block; trim reconstruction to original block length"}
    return Embedding(out, reference, time.perf_counter() - start)


def validate_reference(ref):
    if not isinstance(ref, dict) or ref.get("schema") != SCHEMA:
        raise ValueError("Unsupported reference schema.")
    try:
        fs = sample_rate(ref["sample_rate"])
        n, level = ref["samples"], ref["level"]
        if isinstance(n, bool) or not isinstance(n, int) or not 16 <= n <= MAX_SAMPLES:
            raise ValueError("Invalid reference sample count.")
        band_index(level, ref["band"])
        alpha = ref["strength"]
        if not np.isfinite(alpha) or not 0.001 <= alpha <= 0.5:
            raise ValueError("Invalid reference strength.")
        if (ref["wavelet"], ref["mode"], ref["fft_norm"]) != ("haar", "periodization", "ortho"):
            raise ValueError("Unsupported transform convention.")
        bs = ref["block_size"]
        if bs is not None and (not isinstance(bs, int) or isinstance(bs, bool) or bs < 64 or bs > MAX_SAMPLES or bs % 2**level):
            raise ValueError("Invalid reference block size.")
        step = bs or n
        spans = [(s, min(s + step, n)) for s in range(0, n, step)]
        if len(ref["blocks"]) != len(spans):
            raise ValueError("Invalid reference block layout.")
        count = 0
        for b, (s, e) in zip(ref["blocks"], spans):
            cap = capacity(e-s, level, ref["band"])
            idx = band_index(level, ref["band"])
            pad = ((e-s + 2**level-1)//2**level)*2**level
            m = pad // 2**(level if idx == 0 else int(ref["band"][1:]))
            k = b["count"]
            if (b["start"], b["end"], b["padded"], b["band_length"]) != (s,e,pad,m) or isinstance(k,bool) or not isinstance(k,int) or not 0 <= k <= cap:
                raise ValueError("Invalid reference block dimensions.")
            for key in ("original_real", "original_imag"):
                a = np.asarray(b[key], dtype=float)
                if a.shape != (k,) or not np.all(np.isfinite(a)):
                    raise ValueError("Invalid reference spectrum.")
            count += k
        if count != ref["payload_length"] or count > MAX_SAMPLES:
            raise ValueError("Reference payload count is inconsistent.")
        if ref["capacity_bits"] != sum(capacity(e-s,level,ref["band"]) for s,e in spans):
            raise ValueError("Reference capacity is inconsistent.")
        return fs
    except (KeyError, TypeError, OverflowError) as exc:
        raise ValueError("Malformed reference metadata.") from exc


def reference_bytes(ref):
    validate_reference(ref)
    return json.dumps(ref, indent=2, allow_nan=False).encode("utf-8")


def load_reference(data):
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Reference file is too large.")
    try:
        ref = json.loads(data)
        validate_reference(ref)
        return ref
    except (UnicodeError, json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Reference must be valid UTF-8 JSON.") from exc


def extract(x, fs, ref):
    x = audio_array(x)
    if sample_rate(fs) != validate_reference(ref) or len(x) != ref["samples"]:
        raise ValueError("Extraction requires the original sample rate and exact sample count/alignment. No automatic crop repair.")
    idx = band_index(ref["level"], ref["band"])
    scores = []
    for b in ref["blocks"]:
        coeffs, _ = decompose(x[b["start"]:b["end"]], ref["level"])
        observed = np.fft.rfft(coeffs[idx], norm="ortho")[1:b["count"]+1]
        original = np.asarray(b["original_real"]) + 1j*np.asarray(b["original_imag"])
        direction = np.where(np.abs(original) == 0, 1 + 0j, np.exp(1j * np.angle(original)))
        scores.extend(((observed-original)*np.conj(direction)).real/ref["strength"])
    scores = np.asarray(scores)
    return (scores > 0).astype(np.uint8), scores  # exact zero -> zero, documented tie rule


def wav_bytes(x, fs, bits=16):
    x = audio_array(x)
    fs = sample_rate(fs)
    if bits not in (8,16,24):
        raise ValueError("PCM bit depth must be 8, 16, or 24.")
    scale = 2**(bits-1)
    q = np.rint(x * scale)
    if np.any(q < -scale) or np.any(q > scale-1):
        raise ValueError("PCM conversion would clip; lower audio amplitude.")
    q = q.astype(np.int32)
    if bits == 8:
        raw = (q+128).astype(np.uint8).tobytes()
    elif bits == 16:
        raw = q.astype("<i2").tobytes()
    else:
        raw = ((q[:,None] >> np.array([0,8,16])) & 255).astype(np.uint8).tobytes()
    buf = io.BytesIO()
    with wave.open(buf,"wb") as w:
        w.setnchannels(1); w.setsampwidth(bits//8); w.setframerate(fs); w.writeframes(raw)
    return buf.getvalue()


def read_wav(data, stereo="reject"):
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("WAV exceeds 24 MB upload limit.")
    try:
        fs, raw = wavfile.read(io.BytesIO(data))
    except Exception as exc:
        raise ValueError("Cannot read WAV. Use a valid uncompressed PCM or float WAV.") from exc
    if raw.dtype == np.uint8:
        x = (raw.astype(float)-128)/128
    elif raw.dtype in (np.int16,np.int32):
        x = raw.astype(float)/2**(raw.dtype.itemsize*8-1)
    elif np.issubdtype(raw.dtype,np.floating):
        x = raw.astype(float)
    else:
        raise ValueError("Unsupported WAV sample format.")
    if x.ndim == 2:
        if x.shape[1] != 2 or stereo not in ("mean","left"):
            raise ValueError("Stereo needs explicit left-channel or channel-mean conversion.")
        x = x[:,0] if stereo == "left" else x.mean(axis=1)
    return sample_rate(fs), audio_array(x)


def generate_audio(kind="harmonic", fs=16000, seconds=2.0, seed=17):
    fs = sample_rate(fs)
    n = int(fs*seconds)
    if not 16 <= n <= MAX_SAMPLES:
        raise ValueError("Generated duration is outside sample limits.")
    t = np.arange(n)/fs
    if kind == "silence":
        x = np.zeros(n)
    elif kind == "harmonic":
        x = .30*np.sin(2*np.pi*220*t)+.14*np.sin(2*np.pi*660*t+.2)+.08*np.sin(2*np.pi*1320*t)
        x *= .65+.35*np.sin(2*np.pi*1.7*t)**2
    elif kind == "chirp":
        from scipy.signal import chirp
        x = .43*chirp(t,180,seconds,min(5000,fs*.4))*np.sin(np.pi*np.arange(n)/n)**2
    elif kind == "noise":
        x = np.random.default_rng(seed).normal(0,.12,n)
        x *= min(1,.65/np.max(np.abs(x)))
    else:
        raise ValueError("Unknown generated signal.")
    return audio_array(x)


def image_payload(size=8):
    if size not in (4,8,16,32):
        raise ValueError("Image size must be 4, 8, 16 or 32.")
    r,c = np.indices((size,size))
    image = ((r+c)%2).astype(np.uint8)
    return image.ravel(), {"kind":"image","shape":[size,size],"order":"C"}


def text_payload(text):
    raw = text.encode("utf-8")
    if not raw or len(raw) > 1024:
        raise ValueError("Text must contain 1–1024 UTF-8 bytes.")
    return np.unpackbits(np.frombuffer(raw,dtype=np.uint8)), {"kind":"text","encoding":"utf-8","byte_length":len(raw),"bitorder":"big"}


def recovered_text(bits):
    return np.packbits(bits).tobytes().decode("utf-8",errors="replace")


def payload_png(bits, shape=None):
    bits = payload_bits(bits)
    if shape is None:
        width = min(32,len(bits)); height = (len(bits)+width-1)//width
        arr = np.pad(bits,(0,width*height-len(bits))).reshape(height,width)
    else:
        arr = bits.reshape(shape)
    buf = io.BytesIO()
    Image.fromarray((arr*255).astype(np.uint8)).resize((256,256),Image.Resampling.NEAREST).save(buf,format="PNG")
    return buf.getvalue()


def evaluate(original, observed, expected, recovered=None, scores=None):
    original = np.asarray(original,dtype=float); observed = np.asarray(observed,dtype=float)
    peak = float(np.max(np.abs(observed))) if observed.size else None
    result = {"peak_amplitude":peak,"clipping_count":int(np.sum(np.abs(observed)>=1)),"snr_db":None,"snr_status":"length mismatch",
              "ber":None,"exact_recovery":None,"detected":None,"detection_rule":"at least 32 expected bits and match fraction >=0.90"}
    if original.shape == observed.shape:
        energy = float(np.dot(original,original)); error = float(np.dot(original-observed,original-observed))
        if energy == 0:
            result["snr_status"] = "undefined: silent reference"
        elif error == 0:
            result["snr_status"] = "+infinity: identical arrays"
        else:
            result["snr_db"] = float(10*np.log10(energy/error)); result["snr_status"] = "finite"
    expected = payload_bits(expected)
    if recovered is not None:
        recovered = payload_bits(recovered)
        if len(expected) != len(recovered):
            raise ValueError("Recovered payload length differs from expected.")
        result["ber"] = float(np.mean(expected!=recovered))
        result["exact_recovery"] = bool(np.array_equal(expected,recovered))
        result["detected"] = bool(len(expected)>=32 and result["ber"] <= .1)
        if scores is not None:
            result["minimum_signed_margin"] = float(np.min((2*expected.astype(float)-1)*scores))
    return result
