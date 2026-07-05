# ArcSense — LT Line Break Detection (Software Track)

Detects high-impedance broken-conductor faults on LT lines that conventional
overcurrent breakers cannot see, using symmetrical-component analysis
(the real protection-engineering technique) on simulated 3-phase data,
classified by a Random Forest, served via FastAPI, visualized on a live
dark-theme Dash dashboard.

## What's in here

| File                    | Purpose                                                              |
|--------------------------|-----------------------------------------------------------------------|
| `data_generator.py`      | Synthesizes 3-phase waveforms for 5 scenarios (normal, line_break, motor_startup, capacitor_switch, load_shedding) |
| `feature_extraction.py`  | Computes symmetrical components (V0, V2, unbalance) + RMS/THD/discontinuity/crest features |
| `train_model.py`         | Trains Random Forest, reports per-scenario false positive rate, saves `lineguard_model.pkl` |
| `fastapi_app.py`         | `/ingest`, `/live`, `/alerts`, `/health` API. Publishes fault events via MQTT if a broker is reachable, else falls back to in-memory. On a confirmed break: isolates the segment AND fires a CAP-formatted disaster alert, in parallel |
| `disaster_alert.py`      | Builds a CAP (Common Alerting Protocol) formatted alert — the actual open standard NDMA's SACHET platform uses. Logs the payload locally; does NOT call a real NDMA endpoint (no team has production access to that) |
| `simulator.py`           | Streams simulated sensor-node data into the API continuously; `--force-break` triggers a guaranteed break event for your live demo moment |
| `dashboard.py`           | Dark SCADA-style live dashboard, polls `/live` every 2s — now includes a Disaster Alert Feed panel |

## Run order (3 terminals)

```bash
pip install -r requirements.txt --break-system-packages   # if on a managed system

# 1. Train the model (run once, or whenever you change the generator/features)
python3 train_model.py

# 2. Terminal A — start the API
uvicorn fastapi_app:app --host 0.0.0.0 --port 8000

# 3. Terminal B — start the dashboard
python3 dashboard.py
# open http://localhost:8050 in your browser

# 4. Terminal C — start the live simulator
python3 simulator.py
# during your pitch, in a separate moment, run:
python3 simulator.py --force-break
```

## What to say about the disaster alert feature (be honest here)

`disaster_alert.py` builds a correctly-structured CAP (Common Alerting
Protocol) message — the real standard NDMA's SACHET platform runs on —
the moment a break is confirmed. It logs that payload and shows it on
the dashboard. **It does not call any real NDMA/SACHET endpoint** — no
hackathon team has authorized production access to that. Say exactly
this if asked: "This generates and demonstrates the exact alert payload
our system would send — integration with the live NDMA endpoint requires
authorized agency access, which is the deployment-phase step beyond this
prototype." That is accurate and defensible. Do not imply it is actually
connected to NDMA.

## What to say about the numbers (verified, not guessed)

- Accuracy stays **above 95% with false-positive rate under 0.15%** up to a
  noise level of 0.35 on the synthetic generator, degrading gracefully
  beyond that — not a cliff-edge failure. This was checked across a noise
  sweep (0.04 to 0.70), not a single lucky train/test split.
- Feature importances show RMS-per-phase and crest factor contribute most,
  with sequence components and arc-discontinuity count as supporting
  signals — say this honestly if asked; don't oversell sequence components
  as the sole mechanism.
- This is validated on **synthetic data only**. State that explicitly.
  Field validation against real feeder telemetry (solar inverter harmonics,
  EV charging transients, variable soil resistivity) is the next phase —
  say this before a judge asks it.

## Optional: real MQTT broker

If you want the dashboard to show "MQTT broker connected" instead of the
local fallback, run a broker before starting the API:

```bash
docker run -d -p 1883:1883 eclipse-mosquitto
```

Not required — the system works correctly either way.
