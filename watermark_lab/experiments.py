"""Controlled transformations and complete exports; failures are observations."""
from __future__ import annotations
import csv
import hashlib
import io
import json
import platform
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

import numpy as np
from scipy.signal import butter, resample_poly, sosfiltfilt

from .engine import (embed, extract, evaluate, generate_audio, image_payload, payload_png,
                     read_wav, reference_bytes, wav_bytes, recovered_text)

ATTACKS = ["none", "noise_45dB", "noise_25dB", "gain_0.8", "gain_1.1", "resample_3over4_back",
           "lowpass_2000Hz", "crop_first_1percent", "pcm8", "pcm24", "mp3_128kbps"]


class NotRun(RuntimeError):
    pass


def attack(x, fs, name, seed=20261010):
    x = np.asarray(x,dtype=float)
    if name == "none":
        return x.copy(),fs
    if name.startswith("noise_"):
        db = float(name.removeprefix("noise_").removesuffix("dB"))
        # At silence, use a declared 0.1 RMS nominal carrier, not division by zero.
        rms = np.sqrt(np.mean(x*x)) or .1
        sigma = rms*10**(-db/20)
        return x+np.random.default_rng(seed).normal(0,sigma,len(x)),fs
    if name.startswith("gain_"):
        return x*float(name.removeprefix("gain_")),fs
    if name == "resample_3over4_back":
        y = resample_poly(resample_poly(x,3,4),4,3)
        # Known round-trip duration correction, no watermark-informed alignment.
        return y[:len(x)],fs
    if name == "lowpass_2000Hz":
        return sosfiltfilt(butter(6,2000,fs=fs,output="sos"),x),fs
    if name == "crop_first_1percent":
        return x[max(1,len(x)//100):],fs
    if name in ("pcm8","pcm24"):
        bits = int(name[3:])
        return read_wav(wav_bytes(x,fs,bits))[1],fs
    if name == "mp3_128kbps":
        executable = shutil.which("ffmpeg")
        if not executable:
            raise NotRun("NOT RUN: ffmpeg is unavailable")
        # Keep codec scratch in the project working directory, also on restricted desktops.
        work_root = Path.cwd()/".cache"/"codec"
        try:
            work_root.mkdir(parents=True,exist_ok=True)
        except OSError as exc:
            raise NotRun("NOT RUN: codec scratch directory is not writable") from exc
        with tempfile.TemporaryDirectory(prefix="run-",dir=work_root,ignore_cleanup_errors=True) as directory:
            root = Path(directory)
            if not root.resolve().is_relative_to(work_root.resolve()):
                raise NotRun("NOT RUN: invalid codec scratch path")
            (root/"input.wav").write_bytes(wav_bytes(x,fs))
            commands = [[executable,"-v","error","-y","-i",str(root/"input.wav"),"-c:a","libmp3lame","-b:a","128k",str(root/"coded.mp3")],
                        [executable,"-v","error","-y","-i",str(root/"coded.mp3"),"-c:a","pcm_s16le",str(root/"decoded.wav")]]
            for cmd in commands:
                try:
                    p = subprocess.run(cmd,capture_output=True,timeout=30,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
                except (OSError,subprocess.TimeoutExpired) as exc:
                    raise NotRun(f"NOT RUN: codec tool failed ({type(exc).__name__})") from exc
                if p.returncode:
                    raise NotRun("NOT RUN: ffmpeg/libmp3lame encoding or decoding unavailable")
            decoded_fs,y = read_wav((root/"decoded.wav").read_bytes())
            return y,decoded_fs
    raise ValueError("Unknown attack.")


def one_result(x,fs,bits,strength=.06,band="A2",level=2,block_size=None,payload_info=None):
    t0 = time.perf_counter()
    embedded = embed(x,fs,bits,strength,level,band,block_size)
    saved = wav_bytes(embedded.audio,fs)
    saved_fs,y = read_wav(saved)
    recovered,scores = extract(y,saved_fs,embedded.reference)
    metrics = evaluate(x,y,bits,recovered,scores)
    metrics.update({"embedding_seconds":embedded.seconds,"pipeline_seconds":time.perf_counter()-t0,
                    "capacity_bits":embedded.reference["capacity_bits"],"payload_bits":len(bits),
                    "wav_bytes":len(saved),"pcm_bits":16,"reference_bytes":len(reference_bytes(embedded.reference))})
    return {"original":x,"watermarked":y,"wav":saved,"bits":bits,"recovered":recovered,
            "scores":scores,"reference":embedded.reference,"metrics":metrics,"payload_info":payload_info or {"kind":"bits"}}


def result_archive(result):
    info = result["payload_info"]
    shape = info.get("shape")
    contents = {"original.wav":wav_bytes(result["original"],result["reference"]["sample_rate"]),
                "watermarked.wav":result["wav"], "reference.json":reference_bytes(result["reference"]),
                "metrics.json":json.dumps(result["metrics"],indent=2,allow_nan=False).encode(),
                "payload_info.json":json.dumps(info,indent=2).encode(),
                "original_payload.png":payload_png(result["bits"],shape),
                "recovered_payload.png":payload_png(result["recovered"],shape),
                "recovered_bits.txt":("".join(map(str,result["recovered"]))+"\n").encode(),
                "README.txt":b"Extraction is non-blind: watermarked.wav + reference.json are required. Payload info describes display only. Metrics compare against the input float array; original.wav is a separately quantized convenience copy. No automatic gain/crop alignment.\n"}
    if info["kind"] == "text":
        contents["recovered_text.txt"] = recovered_text(result["recovered"]).encode("utf-8")
    contents["SHA256SUMS.txt"] = "\n".join(f"{hashlib.sha256(value).hexdigest()}  {key}" for key,value in contents.items()).encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as z:
        for key,value in contents.items():
            z.writestr(key,value)
    return buf.getvalue()


def batch(seed=20261010, signals=("harmonic","chirp"), strengths=(.02,.06), bands=("A2","D2","D1"), attacks=None):
    attacks = ATTACKS if attacks is None else attacks
    bits,info = image_payload(8)
    rows = []
    for signal in signals:
        fs = 16000
        x = generate_audio(signal,fs,2,seed)
        for strength in strengths:
            for band in bands:
                run = one_result(x,fs,bits,strength,band,payload_info=info)
                _,control = read_wav(wav_bytes(x,fs))
                for name in attacks:
                    for kind,y in (("watermarked",run["watermarked"]),("unwatermarked",control)):
                        t0 = time.perf_counter()
                        row = {"signal":signal,"strength":strength,"band":band,"attack":name,"kind":kind,"seed":seed,
                               "status":"OK","error":"","payload_bits":len(bits),"capacity_bits":run["metrics"]["capacity_bits"],
                               "embedding_seconds":run["metrics"]["embedding_seconds"],"source_wav_bytes":len(run["wav"])}
                        try:
                            transformed,rate = attack(y,fs,name,seed)
                            row["output_samples"] = len(transformed)
                            row.update(evaluate(x,transformed,bits))
                            # Every transformed candidate is also saved and reloaded as PCM16.
                            saved = wav_bytes(transformed,rate)
                            row["attack_wav_bytes"] = len(saved)
                            reloaded_fs,reloaded = read_wav(saved)
                            row.update(evaluate(x,reloaded,bits))
                            recovered,scores = extract(reloaded,reloaded_fs,run["reference"])
                            row.update(evaluate(x,reloaded,bits,recovered,scores))
                        except NotRun as exc:
                            row["status"] = "NOT RUN"; row["error"] = str(exc)
                        except ValueError as exc:
                            row["status"] = "EXTRACTION FAILED"; row["error"] = str(exc)
                        row["processing_seconds"] = time.perf_counter()-t0
                        rows.append(row)
    return rows


def batch_summary(rows):
    result = {}
    for kind in ("watermarked","unwatermarked"):
        group = [r for r in rows if r["kind"]==kind]
        valid = [r for r in group if r.get("ber") is not None]
        result[kind] = {"rows":len(group),"extractable_rows":len(valid),
                        "not_run":sum(r["status"]=="NOT RUN" for r in group),
                        "failed_extraction":sum(r["status"]=="EXTRACTION FAILED" for r in group),
                        "exact_recoveries":sum(bool(r.get("exact_recovery")) for r in group),
                        "exact_recovery_rate_extractable":sum(bool(r.get("exact_recovery")) for r in valid)/len(valid) if valid else None,
                        "exact_recovery_rate_attempted":sum(bool(r.get("exact_recovery")) for r in group)/(len(group)-sum(r["status"]=="NOT RUN" for r in group)) if any(r["status"]!="NOT RUN" for r in group) else None,
                        "detection_rate_extractable":sum(bool(r.get("detected")) for r in valid)/len(valid) if valid else None}
    return result


def rows_csv(rows):
    keys = list(dict.fromkeys(key for row in rows for key in row))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream,fieldnames=keys); writer.writeheader(); writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def environment():
    import importlib.metadata
    codec = shutil.which("ffmpeg")
    return {"python":platform.python_version(),"platform":platform.platform(),"processor":platform.processor(),
            "versions":{name:importlib.metadata.version(name) for name in ("numpy","scipy","PyWavelets","streamlit","matplotlib")},
            "ffmpeg":subprocess.run([codec,"-version"],capture_output=True,text=True,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)).stdout.splitlines()[0] if codec else "NOT RUN"}


def batch_archive(rows):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("experiments.csv",rows_csv(rows))
        z.writestr("experiments.json",json.dumps(rows,indent=2,allow_nan=False))
        z.writestr("summary.json",json.dumps(batch_summary(rows),indent=2,allow_nan=False))
        z.writestr("environment.json",json.dumps(environment(),indent=2))
    return buf.getvalue()


def block_benchmark(block_size=1024,fs=16000):
    x = generate_audio("harmonic",fs,2)
    bits,_ = image_payload(8)
    run = one_result(x,fs,bits,block_size=block_size)
    blocks = run["reference"]["blocks"]
    times = np.array([b["seconds"] for b in blocks])
    durations = np.array([(b["end"]-b["start"])/fs for b in blocks])
    return {"measurement":"desktop embedding only, single pass; Python/library overhead included in elapsed time",
            "block_size":block_size,"blocks":len(blocks),"mean_ms":float(times.mean()*1000),
            "max_ms":float(times.max()*1000),"nominal_duration_ms":block_size/fs*1000,
            "max_time_to_duration_ratio":float(np.max(times/durations)),
            "max_estimated_array_bytes":max(b["estimated_array_bytes"] for b in blocks),
            "memory_assumptions":"Float64 input + output + DWT coefficients; complex128 one-sided FFT + selected original + directions; int64 bins. Excludes library scratch, interpreter, metadata, allocations, complete file and UI. Not peak RSS or MCU RAM.",
            "saved_pcm16_ber":run["metrics"]["ber"],"reference_bytes":run["metrics"]["reference_bytes"]}


def export_suite(directory, rows=None):
    import os
    os.environ.setdefault("MPLCONFIGDIR",str(Path.cwd()/".cache"/"matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    root = Path(directory); root.mkdir(parents=True,exist_ok=True)
    rows = batch() if rows is None else rows
    (root/"experiments.csv").write_bytes(rows_csv(rows))
    (root/"experiments.json").write_text(json.dumps(rows,indent=2,allow_nan=False),encoding="utf-8")
    (root/"summary.json").write_text(json.dumps(batch_summary(rows),indent=2),encoding="utf-8")
    (root/"batch.zip").write_bytes(batch_archive(rows))
    (root/"environment.json").write_text(json.dumps(environment(),indent=2),encoding="utf-8")
    bits,info = image_payload(8)
    sample = one_result(generate_audio(),16000,bits,payload_info=info)
    (root/"example.zip").write_bytes(result_archive(sample))
    with zipfile.ZipFile(io.BytesIO(result_archive(sample))) as z:
        for name in z.namelist():
            target = root/"example"/name; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(z.read(name))
    (root/"block_benchmarks.json").write_text(json.dumps([block_benchmark(b) for b in (256,1024,4096)],indent=2),encoding="utf-8")
    fig,axes = plt.subplots(2,1,figsize=(11,7),layout="constrained")
    names = ATTACKS
    for band in ("A2","D2","D1"):
        ber=[]; rate=[]
        for name in names:
            group = [r for r in rows if r["kind"]=="watermarked" and r["band"]==band and r["attack"]==name]
            valid = [r["ber"] for r in group if r.get("ber") is not None]
            ber.append(np.mean(valid) if valid else np.nan)
            attempted = [r for r in group if r["status"]!="NOT RUN"]
            rate.append(sum(bool(r.get("exact_recovery")) for r in attempted)/len(attempted) if attempted else np.nan)
        axes[0].plot(range(len(names)),ber,"o-",label=band)
        axes[1].plot(range(len(names)),rate,"o-",label=band)
    axes[0].set(ylabel="Mean BER (extractable rows)",ylim=(-.02,1.02),title="Saved/reloaded PCM16 experiments · 64 bits · two generated signals · two strengths")
    axes[1].set(ylabel="Exact recovery / attempted",ylim=(-.02,1.02),xticks=range(len(names)),xticklabels=names)
    axes[1].tick_params(axis="x",rotation=35)
    for ax in axes: ax.legend(); ax.grid(alpha=.2)
    fig.savefig(root/"robustness.png",dpi=160); plt.close(fig)
    fig,axes = plt.subplots(2,1,figsize=(11,6),layout="constrained")
    t = np.arange(len(sample["original"]))/16000
    for label,x in (("Original",sample["original"]),("Saved watermarked",sample["watermarked"])):
        axes[0].plot(t[:1600],x[:1600],label=label,alpha=.65)
        f = np.fft.rfftfreq(len(x),1/16000)
        axes[1].plot(f,20*np.log10(np.maximum(np.abs(np.fft.rfft(x))/len(x),1e-12)),label=label,alpha=.65)
    axes[0].set(xlabel="Seconds",ylabel="Amplitude",title="Example signal: first 100 ms")
    axes[1].set(xlabel="Hz",ylabel="Magnitude dB re 1",xlim=(0,8000))
    for ax in axes: ax.legend(); ax.grid(alpha=.2)
    fig.savefig(root/"audio_comparison.png",dpi=160); plt.close(fig)
    return rows
