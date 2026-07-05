"""
simulator.py
------------
Mimics 3 sensor nodes on a feeder, each posting a waveform reading to the
API every 2 seconds. Mostly posts 'normal', occasionally injects a
line_break or a false-positive-risk scenario, so the live demo shows
the system correctly staying quiet most of the time and reacting only
when it should.

Run this AFTER fastapi_app.py is running (uvicorn fastapi_app:app --port 8000).
"""

import time
import random
import requests
import sys

sys.path.insert(0, ".")
from data_generator import generate_sample, SCENARIOS

API_URL = "http://localhost:8000/ingest"
NODE_IDS = ["feeder_node_A1", "feeder_node_B2", "feeder_node_C3"]

# Weighted so 'normal' dominates, occasional events of each other type
SCENARIO_WEIGHTS = {
    "normal": 0.70,
    "motor_startup": 0.10,
    "capacitor_switch": 0.08,
    "load_shedding": 0.08,
    "line_break": 0.04,
}


def pick_scenario():
    scenarios = list(SCENARIO_WEIGHTS.keys())
    weights = list(SCENARIO_WEIGHTS.values())
    return random.choices(scenarios, weights=weights, k=1)[0]


def run(interval_seconds=2, n_iterations=None):
    print(f"Simulating {len(NODE_IDS)} feeder nodes -> POST {API_URL} every {interval_seconds}s")
    print("Ctrl+C to stop.\n")
    i = 0
    while n_iterations is None or i < n_iterations:
        node_id = random.choice(NODE_IDS)
        scenario = pick_scenario()
        a, b, c = generate_sample(scenario)
        payload = {"node_id": node_id, "Va": a.tolist(), "Vb": b.tolist(), "Vc": c.tolist()}
        try:
            r = requests.post(API_URL, json=payload, timeout=5)
            result = r.json()
            flag = " <-- FLAGGED" if result["prediction"] == "line_break" else ""
            print(f"[{node_id}] injected={scenario:16s} predicted={result['prediction']:16s}"
                  f" conf={result['confidence']:.2f}{flag}")
        except requests.exceptions.ConnectionError:
            print("Could not reach API — is fastapi_app.py running on port 8000?")
            break
        time.sleep(interval_seconds)
        i += 1


def force_line_break(node_id="feeder_node_A1"):
    """Call this directly for the live demo moment — guarantees a break event."""
    a, b, c = generate_sample("line_break")
    payload = {"node_id": node_id, "Va": a.tolist(), "Vb": b.tolist(), "Vc": c.tolist()}
    r = requests.post(API_URL, json=payload, timeout=5)
    print(r.json())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--force-break":
        force_line_break()
    else:
        run()
