"""Shared advanced DSP interface, used by the simple app and standalone lab."""
import io
import json
import zipfile
from pathlib import Path
import os
os.environ.setdefault("MPLCONFIGDIR",str(Path(__file__).parent/".cache"/"matplotlib"))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from watermark_lab.engine import (capacity, generate_audio, image_payload, text_payload,
                                 payload_png, wav_bytes, read_wav, extract, load_reference,
                                 reference_bytes, recovered_text)
from watermark_lab.experiments import (one_result, result_archive, batch, batch_archive,
                                       batch_summary, block_benchmark, attack, ATTACKS)


def fmt(value,places=2):
    return "Undefined" if value is None else f"{value:.{places}f}"


def plot_audio(x,y,fs):
    fig,axes = plt.subplots(2,1,figsize=(10,5),layout="constrained")
    fig.patch.set_facecolor("#f4f5f0")
    stride = max(1,len(x)//2500)
    for name,a,color in (("Original",x,"#6b8577"),("Saved watermarked",y,"#bc6239")):
        axes[0].plot(np.arange(len(a))[::stride]/fs,a[::stride],label=name,color=color,alpha=.7,linewidth=.7)
        spec = np.fft.rfft(a); freq = np.fft.rfftfreq(len(a),1/fs)
        ss = max(1,len(freq)//3000)
        axes[1].plot(freq[::ss],20*np.log10(np.maximum(np.abs(spec[::ss])/len(a),1e-12)),label=name,color=color,alpha=.75,linewidth=.7)
    axes[0].set(xlabel="Time (s)",ylabel="Amplitude",title="Waveform · display decimated only")
    axes[1].set(xlabel="Frequency (Hz)",ylabel="Magnitude (dB re 1)",title="Spectrum · full signal FFT")
    for ax in axes: ax.legend(loc="upper right"); ax.grid(alpha=.15); ax.set_facecolor("#f4f5f0")
    st.pyplot(fig); plt.close(fig)



def render_advanced_lab():
    st.markdown("""<style>
    .stApp {background:#f4f5f0;color:#192c29} h1,h2,h3 {letter-spacing:-.035em}
    .block-container {padding-top:2rem;max-width:1380px}
    div[data-testid='stMetric'] {background:#e7ede2;border:1px solid #d1ddcf;border-radius:10px;padding:16px}
    div[data-testid='stTabs'] button {font-weight:600}
    .lab-kicker {color:#577163;font-size:.78rem;letter-spacing:.16em;font-weight:700}
    .lab-intro {font-size:1.1rem;color:#53655f;max-width:850px}
    .lab-tag {background:#dce7d4;color:#294b36;padding:5px 11px;border-radius:15px;font-size:.76rem;margin-right:8px}
    </style>""",unsafe_allow_html=True)
    st.markdown('<div class="lab-kicker">SIGNAL PROCESSING / SOFTWARE LAB / 01</div>',unsafe_allow_html=True)
    st.title("Audio Watermark Lab")
    st.markdown('<p class="lab-intro">Embed a small payload. Listen to the result. Measure what survives.<br>A reproducible Haar + FFT experiment with the reference kept in view.</p>',unsafe_allow_html=True)
    st.markdown('<span class="lab-tag">Non-blind extraction</span><span class="lab-tag">Saved PCM16 validation</span><span class="lab-tag">Software DSP</span>',unsafe_allow_html=True)
    st.write("")
    lab,robust,blocks,recovery,notes = st.tabs(["01 · Embed & inspect","02 · Robustness","03 · Block feasibility","04 · Extract a file","05 · Method & evidence"])


    with lab:
        settings,view = st.columns([1,2.1],gap="large")
        with settings:
            st.subheader("Set up an experiment")
            source = st.radio("Audio source",["Generated example","Upload WAV"],horizontal=True,key="audio_source")
            x=None; fs=16000
            if source == "Generated example":
                signal = st.selectbox("Generated audio",["harmonic","chirp","noise","silence"],key="generated_audio")
                duration = st.slider("Duration (seconds)",1,5,2,key="duration")
                x = generate_audio(signal,fs,duration)
            else:
                upload = st.file_uploader("PCM or float WAV (≤24 MB)",type=["wav"],key="audio_upload")
                stereo = st.selectbox("Stereo conversion",["reject","mean","left"],key="stereo_mode")
                if upload:
                    try: fs,x = read_wav(upload.getvalue(),stereo)
                    except ValueError as exc: st.error(str(exc))
            attenuation = st.slider("Input gain for headroom",.1,1.0,1.0,.05,key="input_gain")
            if x is not None: x=x*attenuation
            payload_type = st.radio("Payload",["Binary image","UTF-8 text"],horizontal=True,key="payload_type")
            bits=None; info=None
            if payload_type == "Binary image":
                size = st.selectbox("Image side (pixels)",[4,8,16,32],index=1,key="image_size")
                bits,info=image_payload(size)
            else:
                text = st.text_input("Text to embed",value="DSP LAB",key="payload_text")
                try: bits,info = text_payload(text)
                except ValueError as exc: st.error(str(exc))
            level = st.selectbox("Haar decomposition level",[1,2,3,4],index=1,key="wavelet_level")
            band = st.selectbox("Subband",[f"A{level}"]+[f"D{j}" for j in range(level,0,-1)],key="wavelet_band")
            strength = st.slider("FFT displacement strength",.001,.200,.060,.001,format="%.3f",key="strength")
            use_blocks = st.checkbox("Embed in separate blocks",key="use_blocks")
            block_size = st.selectbox("Block size (samples)",[256,512,1024,2048,4096],index=2,key="block_size") if use_blocks else None
            if x is not None and bits is not None:
                step = block_size or len(x)
                cap = sum(capacity(min(step,len(x)-s),level,band) for s in range(0,len(x),step))
                st.caption(f"{len(bits)} payload bits / {cap:,} available bins · {fs:,} Hz mono · {len(x):,} samples")
            if st.button("Embed · save · reload · extract",type="primary",width="stretch",disabled=x is None or bits is None):
                try:
                    st.session_state.run = one_result(x,fs,bits,strength,band,level,block_size,info)
                except ValueError as exc: st.error(str(exc))
            st.caption("Validated fixture range: PCM16, strength 0.02–0.12, ≤96,000 samples divisible by 4, level 2, A2/D2/D1, ≤256 bits, no attacks, no clipping. Other settings are experiments.")
        with view:
            run=st.session_state.get("run")
            if run is None:
                st.subheader("A small signal. A testable claim.")
                st.info("Choose an audio source and payload, then run the full saved-file pipeline. The recovered bits come from reloaded PCM16 audio.")
                if x is not None:
                    try: st.audio(wav_bytes(x,fs),format="audio/wav")
                    except ValueError as exc: st.warning(str(exc))
                if bits is not None: st.image(payload_png(bits,info.get("shape")),caption=f"Generated payload · {len(bits)} bits",width=220)
                st.markdown("**01** Keep an untouched reference.\n\n**02** Embed in a named Haar subband.\n\n**03** Save the WAV and measure extraction.")
            else:
                m=run["metrics"]; ref=run["reference"]
                st.subheader("Last completed run")
                st.caption(f"{ref['band']} · level {ref['level']} · strength {ref['strength']:.3f} · {m['payload_bits']} bits · {ref['samples']:,} samples · PCM16 · block size {ref['block_size'] or 'whole file'}")
                a,b,c,d=st.columns(4)
                a.metric("Bit error rate",f"{m['ber']:.2%}")
                b.metric("Exact recovery","Yes" if m["exact_recovery"] else "No")
                c.metric("Audio SNR",fmt(m["snr_db"])+(" dB" if m["snr_db"] is not None else ""))
                d.metric("Saved peak",fmt(m["peak_amplitude"],4))
                if m["snr_db"] is None: st.caption(m["snr_status"])
                left,right=st.columns(2)
                left.write("**Original audio**"); left.audio(wav_bytes(run["original"],ref["sample_rate"]),format="audio/wav")
                right.write("**Saved watermarked audio**"); right.audio(run["wav"],format="audio/wav")
                plot_audio(run["original"],run["watermarked"],ref["sample_rate"])
                p,q=st.columns(2)
                p.image(payload_png(run["bits"],run["payload_info"].get("shape")),caption="Original payload",width=180)
                q.image(payload_png(run["recovered"],run["payload_info"].get("shape")),caption="Recovered from saved WAV",width=180)
                if run["payload_info"]["kind"]=="text": st.write("Recovered text:",recovered_text(run["recovered"]))
                st.caption(f"Clipping: {m['clipping_count']} samples · full pipeline {m['pipeline_seconds']*1000:.2f} ms · capacity {m['capacity_bits']:,} bits · WAV {m['wav_bytes']:,} bytes · reference {m['reference_bytes']:,} bytes")
                st.download_button("Download complete experiment",result_archive(run),"audio-watermark-experiment.zip","application/zip",type="primary")
                u,v,w=st.columns(3)
                u.download_button("Watermarked WAV",run["wav"],"watermarked.wav","audio/wav")
                v.download_button("Reference JSON",reference_bytes(ref),"reference.json","application/json")
                w.download_button("Recovered image",payload_png(run["recovered"],run["payload_info"].get("shape")),"recovered_payload.png","image/png")
    with robust:
        st.subheader("What survives a controlled transformation?")
        st.write("Each batch uses two generated signals, three subbands, two strengths and a 64-bit image. Every marked candidate has an unwatermarked control. Every attack output is saved and reloaded before extraction.")
        st.caption("Seed 20261010 · exact expected-payload match is an evaluation rule, not proof of authenticity. Cropping is expected to fail alignment. Missing codecs are labeled NOT RUN.")
        include_codec=st.checkbox("Include MP3 128 kbps (requires ffmpeg)",value=True)
        if st.button("Run reproducible batch",type="primary"):
            with st.spinner("Measuring marked files and controls…"):
                st.session_state.rows=batch(attacks=ATTACKS if include_codec else ATTACKS[:-1])
        rows=st.session_state.get("rows")
        if rows:
            summary=batch_summary(rows); marked=summary["watermarked"]; controls=summary["unwatermarked"]
            a,b,c,d=st.columns(4)
            a.metric("Exact / attempted",f"{marked['exact_recovery_rate_attempted']:.1%}")
            b.metric("Control detections",f"{controls['detection_rate_extractable']:.1%}")
            c.metric("Failed extraction",marked["failed_extraction"])
            d.metric("Codec NOT RUN",marked["not_run"])
            frame=pd.DataFrame(rows)
            chart=frame[(frame.kind=="watermarked") & frame.ber.notna()].groupby(["attack","band"]).ber.mean().unstack()
            st.write("**Mean BER · extractable rows only**"); st.bar_chart(chart)
            st.caption("Failed extractions are listed below and included as failures in exact/attempted. Null BER means no aligned extraction, never zero errors.")
            st.dataframe(frame,width="stretch",hide_index=True)
            st.download_button("Download batch CSV, JSON & environment",batch_archive(rows),"audio-watermark-batch.zip","application/zip")
        else:
            st.info("Run the batch to view measured results. No robustness result is pre-filled.")
        if st.session_state.get("run"):
            st.divider(); st.write("**Try one attack on the last completed run**")
            choice=st.selectbox("Controlled transformation",ATTACKS)
            if st.button("Measure this transformation"):
                from watermark_lab.engine import evaluate
                run=st.session_state.run; rate=run["reference"]["sample_rate"]
                try:
                    y,rate=attack(run["watermarked"],rate,choice)
                    rate,y=read_wav(wav_bytes(y,rate))
                    recovered,scores=extract(y,rate,run["reference"])
                    st.json(evaluate(run["original"],y,run["bits"],recovered,scores))
                except (ValueError,RuntimeError) as exc: st.warning(str(exc))
    with blocks:
        st.subheader("Desktop timing, explicit resource assumptions")
        st.write("A payload is distributed across consecutive independent blocks. No real-time audio capture or hardware deployment is implemented.")
        size=st.select_slider("Benchmark block size",[256,512,1024,2048,4096],value=1024)
        if st.button("Measure desktop blocks",type="primary"):
            st.session_state.benchmark=block_benchmark(size)
        measure=st.session_state.get("benchmark")
        if measure:
            a,b,c,d=st.columns(4)
            a.metric("Mean processing",f"{measure['mean_ms']:.3f} ms")
            b.metric("Max processing",f"{measure['max_ms']:.3f} ms")
            c.metric("Nominal block duration",f"{measure['nominal_duration_ms']:.2f} ms")
            d.metric("Array estimate",f"{measure['max_estimated_array_bytes']:,} B")
            st.json(measure)
            st.download_button("Download measurement",json.dumps(measure,indent=2),"desktop-block-measurement.json","application/json")
        st.warning("Desktop measurements and array estimates cannot establish ESP32 or STM32 timing, memory use, or real-time feasibility.")
    with recovery:
        st.subheader("Extract using an exported reference")
        st.write("Required: a mono candidate WAV with matching sample rate, sample count and alignment, plus the reference JSON from the same embedding run. The expected payload is not needed to extract bits.")
        a,b=st.columns(2)
        wav=a.file_uploader("Candidate WAV",type=["wav"],key="extract_wav")
        metadata=b.file_uploader("Reference JSON",type=["json"],key="extract_json")
        if st.button("Extract uploaded file",type="primary",disabled=wav is None or metadata is None):
            try:
                ref=load_reference(metadata.getvalue()); fs,x=read_wav(wav.getvalue()); bits,scores=extract(x,fs,ref)
                if not len(bits): raise ValueError("Reference contains no payload.")
                st.session_state.extraction={"bits":bits,"scores":scores}
            except ValueError as exc: st.error(str(exc))
        extracted=st.session_state.get("extraction")
        if extracted:
            bits=extracted["bits"]
            st.image(payload_png(bits),caption="Recovered bits laid out in rows of up to 32 · original shape needs payload_info.json",width=250)
            st.write(f"{len(bits)} recovered bits. BER and authenticity cannot be determined without an expected payload.")
            st.download_button("Download recovered bits","".join(map(str,bits))+"\n","recovered_bits.txt","text/plain")
    with notes:
        st.subheader("Read the assumptions with the results")
        st.markdown("""The original MATLAB work was reviewed read-only. Its extraction reference was already modified; one-sided full-FFT edits violated conjugate symmetry; output normalization changed the reference scale; the two detail bands were mislabeled. No SVD call was present. The Arduino sketch uploads files to SD and implements no watermark DSP.

    The corrected method uses Haar coefficients ordered **A₂, D₂, D₁** at level 2. Selected positive-frequency bins carry signed displacements. Their unmodified complex coefficients are stored in the reference. Extraction projects the observed difference onto the original phase direction and takes its sign.

    **Limits:** no blind extraction, cryptographic authenticity, proven inaudibility, universal attack resistance, or embedded-board benchmark. No automatic gain correction or crop repair. Silent-reference SNR is undefined. An expected-payload detector can falsely accept degenerate payloads; batch controls cover the balanced image only.
    """)
        for label,name in (("Algorithm and equations","ALGORITHM.md"),("Original-code review","ORIGINAL_CODE_REVIEW.md"),("Validation and failures","VALIDATION.md"),("Hosting instructions","HOSTING.md"),("Demo and interview notes","DEMO_AND_INTERVIEW.md")):
            path=Path(__file__).parent/"docs"/name
            if path.exists():
                with st.expander(label): st.markdown(path.read_text(encoding="utf-8"))
    st.divider()
    st.caption("Audio Watermark Lab · no API keys · software measurements, stated limits")
