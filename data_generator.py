"""
data_generator.py
------------------
Generates synthetic 3-phase current waveforms for 5 scenarios on an LT feeder.

WHY 3-PHASE (not single-phase like a naive toy model):
A real LT line break is almost always a SINGLE conductor opening while the
other two phases stay healthy. That creates a genuine phase IMBALANCE —
which is exactly what negative-sequence / zero-sequence protection relays
are designed to detect in real substations. Modeling only one phase loses
this physics entirely. Modeling 3 phases lets us compute REAL symmetrical
components (Fortescue transform) as a feature, which is the legitimate,
literature-grounded technique — not an invented one.

Scenarios:
  0 = normal           : balanced 3-phase, no imbalance
  1 = line_break        : phase C opens intermittently (arc restrike pattern)
  2 = motor_startup      : balanced inrush, decaying — should NOT trigger
  3 = capacitor_switch    : balanced short oscillatory transient — should NOT trigger
  4 = load_shedding      : balanced clean amplitude drop — should NOT trigger
"""

import numpy as np

FS = 10_000          # sample rate (Hz)
F0 = 50              # India grid fundamental frequency (Hz)
WINDOW_S = 0.1       # 100 ms window = 5 cycles at 50Hz
N = int(FS * WINDOW_S)
T = np.linspace(0, WINDOW_S, N, endpoint=False)

SCENARIOS = ["normal", "line_break", "motor_startup", "capacitor_switch", "load_shedding"]


def _base_three_phase(amplitude=1.0):
    """Balanced healthy 3-phase sinusoid set, 120 degrees apart."""
    a = amplitude * np.sin(2 * np.pi * F0 * T)
    b = amplitude * np.sin(2 * np.pi * F0 * T - 2 * np.pi / 3)
    c = amplitude * np.sin(2 * np.pi * F0 * T + 2 * np.pi / 3)
    return a, b, c


def _add_noise(x, noise_level):
    return x + noise_level * np.random.randn(len(x))


def generate_sample(scenario, noise_level=0.04):
    """Returns (Va, Vb, Vc) arrays of length N for the given scenario."""
    a, b, c = _base_three_phase()

    if scenario == "normal":
        pass  # balanced, untouched

    elif scenario == "line_break":
        # Phase C conductor opens. Real broken conductors don't decay smoothly —
        # they make/break contact intermittently (arc restrike). Model this as
        # random burst dropouts: short windows where phase C collapses toward
        # near-zero with erratic residual arcing, interspersed with brief
        # partial re-contact.
        mask = np.ones(N)
        n_bursts = np.random.randint(4, 9)
        for _ in range(n_bursts):
            start = np.random.randint(0, N - 40)
            length = np.random.randint(15, 40)
            mask[start:start + length] *= np.random.uniform(0.0, 0.25)
        c = c * mask
        # slight residual high-frequency arc noise on the broken phase only
        c = c + 0.15 * np.random.randn(N) * (1 - mask)

    elif scenario == "motor_startup":
        # Balanced inrush across all 3 phases — decaying envelope, no imbalance
        envelope = 5 * np.exp(-T * 10) + 1
        a, b, c = a * envelope, b * envelope, c * envelope

    elif scenario == "capacitor_switch":
        # Balanced short damped oscillatory transient near a switching instant
        # (LC resonance burst, NOT a sustained harmonic offset)
        switch_t = WINDOW_S * np.random.uniform(0.2, 0.5)
        f_res = np.random.uniform(300, 600)  # resonant frequency, Hz
        pulse = 0.6 * np.exp(-80 * np.abs(T - switch_t)) * np.sin(2 * np.pi * f_res * (T - switch_t))
        a, b, c = a + pulse, b + pulse, c + pulse

    elif scenario == "load_shedding":
        # Balanced, clean step-down in amplitude. No discontinuity, no imbalance.
        drop_t = WINDOW_S * np.random.uniform(0.3, 0.6)
        step = np.where(T < drop_t, 1.0, np.random.uniform(0.2, 0.5))
        a, b, c = a * step, b * step, c * step

    else:
        raise ValueError(f"Unknown scenario: {scenario}")

    a, b, c = _add_noise(a, noise_level), _add_noise(b, noise_level), _add_noise(c, noise_level)
    return a, b, c


def generate_dataset(n_per_class=2000, noise_level=0.04, seed=42):
    """Returns list of dicts: {scenario, Va, Vb, Vc}"""
    np.random.seed(seed)
    rows = []
    for scenario in SCENARIOS:
        for _ in range(n_per_class):
            a, b, c = generate_sample(scenario, noise_level)
            rows.append({"scenario": scenario, "Va": a, "Vb": b, "Vc": c})
    np.random.shuffle(rows)
    return rows


if __name__ == "__main__":
    rows = generate_dataset(n_per_class=5)
    print(f"Generated {len(rows)} samples across {len(SCENARIOS)} scenarios")
    for s in SCENARIOS:
        count = sum(1 for r in rows if r["scenario"] == s)
        print(f"  {s}: {count} samples, each shape {rows[0]['Va'].shape}")
