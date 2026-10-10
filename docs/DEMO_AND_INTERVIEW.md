# 90-second demo

| Time | Action and narration |
|---|---|
| 0–12 s | Open the local lab. “This is a software-only, non-blind Haar/FFT watermarking lab. I reviewed two MATLAB scripts and an Arduino uploader; none implemented SVD.” |
| 12–28 s | Leave harmonic audio, 8×8 image, level 2, A2 and strength 0.06. Run the saved-file pipeline. “The reference keeps the original coefficients. The decoder reads saved PCM16, so this includes file quantization.” |
| 28–42 s | Show BER, exact recovery, SNR and clipping; compare payload images. “These are measured results for this file and operating point. They do not prove inaudibility.” |
| 42–52 s | Play short portions of original and saved watermarked audio. Show waveform and spectrum. “Listening is illustrative; I did not conduct a controlled perceptual study.” |
| 52–64 s | Download the experiment and point to reference JSON. “Extraction needs the reference, matching length and alignment. It does not need expected bits to recover a bit vector.” |
| 64–78 s | Show completed robustness batch (pre-run it before the demo). Point to crop failure and failed payload recovery. “Both marked files and unwatermarked controls receive the same attacks. Failures remain in CSV and JSON.” |
| 78–90 s | Open block feasibility and a completed measurement. “These timings are from desktop Python. Array sizes are documented estimates, not MCU measurements. No board was flashed.” |

## Interview notes

**Why non-blind?** The decoded variable is a difference from original complex coefficients. The original scripts already relied on original information, but overwrote it. The exported selected-coefficient reference makes that dependency usable and explicit. A blind method would need a separately designed encoding/detector and its own validation.

**Why a real FFT?** A full FFT of real samples has conjugate pairs. Editing only positive bins then taking the real part of IFFT changes the desired embedding. Real FFT/inverse FFT handles the conjugate partner; DC/Nyquist stay untouched. The independent fixture verifies cosine synthesis and Parseval distortion energy.

**Why signed displacement?** ±α encodes both bit values. Projecting the complex difference onto the original phase direction remains defined even when a negative displacement crosses zero. The equation is deliberately different from faulty magnitude subtraction. Strength is an absolute orthonormal FFT quantity, not a relative percentage.

**Why save and reload?** PCM changes samples. Passing a floating-point in-memory test would not demonstrate saved-file recovery. Quantization is bounded for the no-attack baseline; measurements use the actual reloaded signal.

**Distortion tradeoff?** In untrimmed ideal blocks, error energy is 2Pα². More bits or larger α adds distortion. SNR measures aggregate error, not perceptual acceptability. A lower α can make quantization/noise overwhelm the sign. Raw capacity means available bins, not a quality guarantee.

**Failure modes?** Gain shifts reference coefficients; filtering/resampling affect subbands and phases; noise affects signs; cropping breaks alignment; MP3 changes content. The current decoder applies no gain estimation, synchronization repair, redundancy or error correction. Recording attack failures is a valid completed experiment, not a reason to alter expected bits.

**Detector false positives?** Match fraction uses an expected payload. Balanced-image controls quantify the suite only. An all-zero expected payload on unwatermarked silence is a demonstrated false positive because zero scores decode to zero. Detection is not authenticity, and the reference is neither encrypted nor signed.

**Embedded feasibility?** Timing compares desktop per-block embedding with B/fs seconds of audio; buffer estimates sum documented float64/complex128 arrays. Python overhead, FFT scratch and complete-file/UI storage are outside that array estimate. Real MCU work would need fixed/float32 precision decisions, memory profiling, compiler/FFT library choices, DMA/I/O scheduling and board measurements. There is no real-time audio stream or hardware validation here.

**How did you verify it?** Independent pairwise Haar arithmetic, explicit DFT synthesis, Parseval, separate metric formulas, PCM8/16/24 error bounds, saved/reloaded known payloads across a documented range, malformed-file/schema checks, reproducible attacks, unwatermarked controls, export consistency, application interaction tests and a browser walkthrough. See validation evidence for actual counts.

## Two truthful CV bullets

- Built a local Python/Streamlit audio watermarking lab with reference-dependent Haar/FFT embedding, saved-and-reloaded PCM16 extraction, interactive audio/payload inspection and reproducible downloadable experiments.
- Reviewed and corrected MATLAB extraction, FFT symmetry and wavelet-indexing defects; implemented automated DSP validation, seeded attack experiments with unwatermarked controls, and desktop block-timing/resource estimates without claiming hardware deployment.
