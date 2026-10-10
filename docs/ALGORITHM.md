# Corrected non-blind Haar/FFT baseline

This baseline is a new, mathematically specified replacement for the faulty extraction equations in the original scripts. It uses signed complex FFT displacement, rather than subtracting magnitudes that were already modified. It implements no SVD, coding gain, secret key, psychoacoustic model or blind extraction.

## Signal and transform conventions

Input is finite, real float64 mono audio with peak below 1, integer sample rate 8–96 kHz and 16–2,880,000 samples. The UI rejects stereo unless the user explicitly chooses the left channel or arithmetic channel mean. The result is always mono; the other stereo channel is not watermarked or preserved. Opposite-phase stereo channels can cancel under channel-mean conversion.

For Haar level L, each block is zero-padded at its end to a multiple of 2^L before the `periodization` DWT. Reconstruction is trimmed to the original block length. Trimming can disturb the embedding at non-divisible lengths; these lengths are accepted as exploratory inputs but are outside the guaranteed range. No-watermark reconstruction still preserves their original length and values. In block mode, payload bits are distributed consecutively, filling each block's capacity before using the next; no repetition or error correction is applied. Blocks without remaining bits are reconstructed unchanged.

For a pair of samples:

$$a_j=(x_{2j}+x_{2j+1})/\sqrt{2},\qquad d_j=(x_{2j}-x_{2j+1})/\sqrt{2}.$$

The coefficient list is `[A_L, D_L, D_(L-1), …, D_1]`. Level 2 is `[A2, D2, D1]`. D_j appears at list index L−j+1. Haar bands are not brick-wall frequency filters; a subband's FFT frequency describes its decimated coefficient sequence.

Let the selected subband have M coefficients c. Use the unitary FFT:

$$X_k=\frac{1}{\sqrt{M}}\sum_{j=0}^{M-1}c_j e^{-2\pi i jk/M}.$$

Eligible bins are k=1,…,floor((M−1)/2): exclude DC and the Nyquist bin for even M. Capacity is floor((M−1)/2) bits per block, and the sum of this quantity over blocks in block mode. This is raw bin capacity, not an audibility or reliability guarantee. One bit uses one positive-frequency bin and its implied negative-frequency conjugate. Payload uses the first P eligible bins, with no random or adaptive selection.

## Embedding and extraction

For bit b_k∈{0,1}, set s_k=2b_k−1 and u_k=exp(i arg X_k), with u_k=1 when X_k=0. Strength α is an absolute displacement in orthonormal FFT units.

$$X'_k=X_k+\alpha s_k u_k.$$

If the coefficient passes through zero under a negative displacement, the phase may flip; the method remains defined because extraction uses coherent signed projection, not an absolute magnitude difference. `irfft(X', n=M, norm="ortho")` reconstructs a real subband and enforces the conjugate partner automatically. Original DC/Nyquist are not changed. Inverse Haar reconstruction yields y. For divisible block lengths, Parseval gives ideal distortion energy:

$$\|y-x\|_2^2=2P\alpha^2.$$

The engine rejects an output peak at or above 1−1/32768. It does not normalize or clip. PCM16 uses q=round(32768y), stores signed integers and reloads q/32768. Full-scale input and any conversion that would clip are rejected. The input gain control is an explicit preparation step; metrics compare the prepared mono input to the saved watermarked signal.

After reloading, compute the same subband and FFT, giving Y. The decoder uses:

$$z_k=\operatorname{Re}[(Y_k-X_k)\overline{u_k}]/\alpha,\qquad \hat b_k=\mathbf{1}[z_k>0].$$

Exactly zero decodes to zero. Unattacked ideal scores are −1 and +1. **Required reference:** selected unmodified complex X_k values, α, sample rate, exact sample count, Haar level, named subband, wavelet/mode/FFT conventions, padding and block layout. u_k is reconstructed from X_k. The full original audio and expected bits are not required for decoding. Expected bits are required for BER, exact-recovery evaluation and the match-based detection rule. The JSON contains no expected bits. Display dimensions/text encoding live separately in `payload_info.json`.

## Supported operating range

The recovery assertion applies to no-attack PCM16 operation with L=2, A2/D2/D1, N≤96,000 divisible by 4, α from 0.02 to 0.12, up to 256 payload bits within capacity, finite input, and output satisfying the headroom check. Generated regression fixtures cover 8/16/48 kHz, harmonic/noise/silence and payload lengths 16/64/256 at three strengths. Other levels, strengths, longer files, boundary-trimmed inputs and attacks are exploratory. Block regression fixtures cover 256/1024/4096 samples at 16 kHz with the default 64-bit payload.

For untrimmed orthonormal transforms the PCM16 error per sample is bounded by 1/(2·32768), so by Cauchy–Schwarz the projected error at a bin is at most √N/(2·32768). At N=96,000 this is less than 0.00473, below the minimum α=0.02. Thus quantization alone cannot flip a bit in that operating range, apart from negligible floating-point error. This bound assumes no rescaling, clipping, attack, or missing padded samples. It is not a noise-robustness proof.

## Metrics and detector limits

BER is number of unequal recovered/expected bits divided by P; exact recovery is an all-bit equality flag. Batch exact recovery is reported with both extractable and attempted denominators. Failed extraction contributes failure to attempted counts; NOT RUN is excluded. Audio SNR is 10 log10(Σx²/Σ(y−x)²). Silent-reference SNR is undefined even if the watermark adds energy. Identical non-silent arrays give +infinity, exported as null plus a status string. Different lengths have null SNR and a length-mismatch status. Peak is max |y|, clipping count counts |y|≥1, bytes are measured from actual files, and time uses a desktop monotonic clock.

An evaluation detector accepts ≥32 expected bits if match fraction ≥0.90. It is only a comparison rule. Unwatermarked silence yields zero scores and zero bits; an all-zero expected payload can therefore falsely accept. Tests explicitly reproduce this hazard. The balanced checkerboard controls measure empirical false positives in this suite, not a population false-positive bound or proof of watermark presence. Integrity hashes in export bundles detect accidental file changes; they are not signed authenticity evidence.

Transform details: [PyWavelets DWT ordering](https://pywavelets.readthedocs.io/en/latest/ref/dwt-discrete-wavelet-transform.html), [NumPy real FFT](https://numpy.org/doc/stable/reference/generated/numpy.fft.rfft.html), [SciPy WAV integer handling](https://docs.scipy.org/doc/scipy/reference/generated/scipy.io.wavfile.read.html). The 24-bit SciPy loader returns left-justified int32 data, so dividing by 2^31 gives the normalized sample value. No guarantees about perceived audibility are made.
