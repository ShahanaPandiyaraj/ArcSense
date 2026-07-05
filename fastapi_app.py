"""
fastapi_app.py
--------------
Ingest endpoint + fault event pipeline + simulated breaker actuation.

DESIGN CHOICE — EventBus abstraction:
Real MQTT pub/sub demonstrates a genuine deployable architecture (sensor
nodes -> broker -> control room). But a hackathon demo dying because a
Mosquitto broker isn't running on the laptop is a completely avoidable
failure. EventBus tries MQTT if a broker is reachable; if not, it falls
back to an in-memory event log automatically. You get the real pub/sub
story in your architecture diagram without a single point of failure
on demo day.
"""

from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime, timezone
from collections import deque
import joblib
import numpy as np

from feature_extraction import extract_features, FEATURE_NAMES
from disaster_alert import publish_disaster_alert, get_recent_alerts

MQTT_BROKER_HOST = "localhost"
MQTT_BROKER_PORT = 1883
MQTT_TOPIC = "arcsense/faults"


class EventBus:
    def __init__(self):
        self.mqtt_client = None
        self.connected = False
        self.local_log = deque(maxlen=200)
        self._try_connect_mqtt()

    def _try_connect_mqtt(self):
        try:
            import paho.mqtt.client as mqtt
            client = mqtt.Client()
            client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=2)
            client.loop_start()
            self.mqtt_client = client
            self.connected = True
            print("[EventBus] Connected to MQTT broker.")
        except Exception as e:
            print(f"[EventBus] No MQTT broker reachable ({e}). "
                  f"Falling back to in-memory event bus — demo will still work.")
            self.connected = False

    def publish(self, topic, payload: dict):
        self.local_log.appendleft(payload)  # always log locally regardless
        if self.connected and self.mqtt_client:
            try:
                import json
                self.mqtt_client.publish(topic, json.dumps(payload))
            except Exception as e:
                print(f"[EventBus] MQTT publish failed, payload still logged locally: {e}")

    def recent_events(self, limit=20):
        return list(self.local_log)[:limit]


app = FastAPI(title="ArcSense — LT Line Break Detection API")
event_bus = EventBus()
model = joblib.load("lineguard_model.pkl")

node_status = {}   # node_id -> {"status": "live"/"isolated", "last_seen": ...}
recent_predictions = deque(maxlen=50)


class SensorReading(BaseModel):
    node_id: str
    Va: list[float]
    Vb: list[float]
    Vc: list[float]
    latitude: float | None = None
    longitude: float | None = None
    area_description: str | None = None


@app.post("/ingest")
def ingest_sensor_data(reading: SensorReading):
    Va, Vb, Vc = np.array(reading.Va), np.array(reading.Vb), np.array(reading.Vc)
    feats = extract_features(Va, Vb, Vc)
    prediction = model.predict([feats])[0]
    proba = model.predict_proba([feats])[0]
    confidence = float(max(proba))

    now = datetime.now(timezone.utc).isoformat()
    node_status[reading.node_id] = {
        "status": "isolated" if prediction == "line_break" else "live",
        "last_prediction": prediction,
        "last_seen": now,
    }

    record = {
        "node_id": reading.node_id,
        "prediction": prediction,
        "confidence": round(confidence, 3),
        "timestamp": now,
    }
    recent_predictions.appendleft(record)

    if prediction == "line_break":
        event_bus.publish(MQTT_TOPIC, record)
        # actuation: in real deployment this calls a relay/contactor driver.
        # here it flips the simulated breaker state, which is what the
        # dashboard and /live endpoint reflect.
        print(f"[ACTUATION] Node {reading.node_id}: ISOLATING segment (simulated breaker open)")

        # disaster-alert pipeline: fires in parallel with isolation, not
        # instead of it. Formatted as CAP — the standard NDMA's SACHET
        # platform uses — but logged locally here, not sent to any real
        # government endpoint.
        publish_disaster_alert(
            node_id=reading.node_id,
            prediction=prediction,
            confidence=confidence,
            latitude=reading.latitude,
            longitude=reading.longitude,
        )

    return {"node_id": reading.node_id, "prediction": prediction, "confidence": confidence}


@app.get("/live")
def live_status():
    return {
        "nodes": node_status,
        "recent_predictions": list(recent_predictions)[:20],
        "recent_faults": event_bus.recent_events(20),
        "mqtt_connected": event_bus.connected,
        "recent_disaster_alerts": get_recent_alerts(10),
    }


@app.get("/alerts")
def alerts():
    """Dedicated endpoint for the CAP-formatted disaster alert feed."""
    return {"alerts": get_recent_alerts(50)}


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": model is not None}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
