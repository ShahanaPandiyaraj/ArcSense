"""
feature_extraction.py
----------------------
Extracts features from 3-phase waveform windows.

Core technique: SYMMETRICAL COMPONENTS (Fortescue transform).
This is the actual method used in real protection relays to detect
broken-conductor / open-phase faults. A balanced 3-phase system has
zero negative-sequence (V2) and zero zero-sequence (V0) component.
A single-phase open-conductor fault breaks that balance and produces
a measurable V2 and/or V0 — independent of whether current magnitude
crosses any overcurrent threshold. This is WHY this technique catches
faults a simple breaker cannot.

Steps:
  1. Extract the fundamental-frequency (50Hz) phasor for each phase via FFT.
  2. Apply the Fortescue transform to get V0 (zero-seq), V1 (positive-seq),
     V2 (negative-seq) phasors.
  3. Compute |V0|, |V2|, and the negative-sequence unbalance factor |V2|/|V1|
     (this exact ratio is a standard power-quality/protection metric).
  4. Add supporting time-domain features: RMS, crest factor, THD,
     and a discontinuity/arc-burst count (catches intermittent arcing
     that a single-frequency-domain snapshot can miss).
"""

import numpy as np
from data_generator import FS, F0, N


def _fundamental_phasor(waveform, fs=FS, f0=F0):
    """Complex phasor (magnitude + phase) of the waveform at the fundamental frequency."""
    n = len(waveform)
    freqs = np.fft.rfftfreq(n, d=1 / fs)
    fft_vals = np.fft.rfft(waveform)
    idx = int(np.argmin(np.abs(freqs - f0)))
    phasor = fft_vals[idx] * 2 / n
    return phasor


def _symmetrical_components(Va_phasor, Vb_phasor, Vc_phasor):
    """Fortescue transform: returns (V0, V1, V2) complex phasors."""
    a = np.exp(1j * 2 * np.pi / 3)
    a2 = np.exp(1j * 4 * np.pi / 3)
    V0 = (Va_phasor + Vb_phasor + Vc_phasor) / 3
    V1 = (Va_phasor + a * Vb_phasor + a2 * Vc_phasor) / 3
    V2 = (Va_phasor + a2 * Vb_phasor + a * Vc_phasor) / 3
    return V0, V1, V2


def _thd(waveform, fs=FS, f0=F0, n_harmonics=5):
    """Total harmonic distortion using harmonics 2 through n_harmonics."""
    n = len(waveform)
    freqs = np.fft.rfftfreq(n, d=1 / fs)
    fft_mags = np.abs(np.fft.rfft(waveform)) * 2 / n
    fund_idx = int(np.argmin(np.abs(freqs - f0)))
    fund_mag = fft_mags[fund_idx] + 1e-9
    harm_energy = 0.0
    for h in range(2, n_harmonics + 1):
        idx = int(np.argmin(np.abs(freqs - f0 * h)))
        harm_energy += fft_mags[idx] ** 2
    return np.sqrt(harm_energy) / fund_mag


def _discontinuity_count(waveform, threshold=0.5):
    """Counts abrupt sample-to-sample jumps — catches intermittent arc bursts."""
    d = np.abs(np.diff(waveform))
    return int(np.sum(d > threshold))


def _crest_factor(waveform):
    rms = np.sqrt(np.mean(waveform ** 2)) + 1e-9
    peak = np.max(np.abs(waveform))
    return peak / rms


FEATURE_NAMES = [
    "V0_mag", "V2_mag", "neg_seq_unbalance",
    "rms_a", "rms_b", "rms_c",
    "thd_a", "thd_b", "thd_c",
    "discontinuity_a", "discontinuity_b", "discontinuity_c",
    "crest_factor_max",
]


def extract_features(Va, Vb, Vc):
    """Returns a 1D feature vector (list of floats) in FEATURE_NAMES order."""
    Va_ph = _fundamental_phasor(Va)
    Vb_ph = _fundamental_phasor(Vb)
    Vc_ph = _fundamental_phasor(Vc)

    V0, V1, V2 = _symmetrical_components(Va_ph, Vb_ph, Vc_ph)
    v0_mag = float(np.abs(V0))
    v2_mag = float(np.abs(V2))
    v1_mag = float(np.abs(V1)) + 1e-9
    neg_seq_unbalance = v2_mag / v1_mag

    rms_a = float(np.sqrt(np.mean(Va ** 2)))
    rms_b = float(np.sqrt(np.mean(Vb ** 2)))
    rms_c = float(np.sqrt(np.mean(Vc ** 2)))

    thd_a, thd_b, thd_c = float(_thd(Va)), float(_thd(Vb)), float(_thd(Vc))

    disc_a = _discontinuity_count(Va)
    disc_b = _discontinuity_count(Vb)
    disc_c = _discontinuity_count(Vc)

    crest_max = max(_crest_factor(Va), _crest_factor(Vb), _crest_factor(Vc))

    return [
        v0_mag, v2_mag, neg_seq_unbalance,
        rms_a, rms_b, rms_c,
        thd_a, thd_b, thd_c,
        disc_a, disc_b, disc_c,
        crest_max,
    ]


if __name__ == "__main__":
    from data_generator import generate_sample, SCENARIOS
    print(f"{'scenario':18s} | V0_mag | V2_mag | unbalance | disc(a,b,c) | crest")
    for s in SCENARIOS:
        feats = []
        for _ in range(20):
            a, b, c = generate_sample(s)
            feats.append(extract_features(a, b, c))
        feats = np.array(feats)
        means = feats.mean(axis=0)
        print(f"{s:18s} | {means[0]:.3f}  | {means[1]:.3f}  | {means[2]:.3f}     | "
              f"({means[9]:.1f},{means[10]:.1f},{means[11]:.1f}) | {means[12]:.2f}")
