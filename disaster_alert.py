"""
disaster_alert.py
------------------
Formats a fault-detection event as a CAP (Common Alerting Protocol) message —
the actual open standard NDMA's SACHET platform is built on. This does NOT
call any real NDMA/SACHET endpoint (no hackathon team has production access
to that), it builds the correctly-structured payload and logs it, so you can
demonstrate the integration contract honestly: "here is exactly what we would
send, in the format the receiving system expects."

Be upfront about this distinction in your pitch: this is a CAP-formatted
alert generator ready for integration, not a live connection to NDMA.
"""

import json
from datetime import datetime, timezone
from collections import deque

SENDER_ID = "arcsense@discom.gov.in"  # placeholder — real deployment uses an authorized agency ID
recent_alerts = deque(maxlen=100)


def build_cap_alert(node_id: str, prediction: str, confidence: float,
                     latitude: float = None, longitude: float = None,
                     area_description: str = "Unspecified feeder segment"):
    """
    Builds a CAP-structured alert dict for a confirmed line_break event.
    Field names follow the CAP v1.2 standard structure (identifier, sender,
    sent, status, msgType, scope, info block with category/event/urgency/
    severity/certainty/headline/description/area).
    """
    now = datetime.now(timezone.utc)
    alert = {
        "identifier": f"ARCSENSE-{node_id}-{int(now.timestamp())}",
        "sender": SENDER_ID,
        "sent": now.isoformat(),
        "status": "Actual",
        "msgType": "Alert",
        "scope": "Public",
        "info": {
            "category": "Infra",
            "event": "Live Conductor Break — LT Distribution Line",
            "urgency": "Immediate",
            "severity": "Severe",
            "certainty": "Observed",
            "confidence_score": round(confidence, 3),
            "headline": f"Broken live conductor detected at node {node_id}",
            "description": (
                f"Automated detection identified a high-impedance broken-conductor "
                f"fault at feeder node {node_id}. Segment has been automatically "
                f"isolated. Conductor may still carry residual charge or be in "
                f"contact with ground — do not approach."
            ),
            "instruction": "Maintain safe distance from the affected line segment. "
                            "Utility response team has been notified for physical inspection.",
            "area": {
                "areaDesc": area_description,
                "latitude": latitude,
                "longitude": longitude,
            },
        },
    }
    return alert


def publish_disaster_alert(node_id: str, prediction: str, confidence: float,
                            latitude: float = None, longitude: float = None):
    """
    'Publishes' the alert — in this prototype, that means logging it and
    storing it for the dashboard/API to display. Swap the body of this
    function for a real HTTP POST to NDMA's CAP ingestion endpoint once
    you have authorized access; the payload format itself does not change.
    """
    alert = build_cap_alert(node_id, prediction, confidence, latitude, longitude)
    recent_alerts.appendleft(alert)
    print(f"[DISASTER ALERT — CAP FORMAT, NOT SENT TO REAL NDMA ENDPOINT]\n"
          f"{json.dumps(alert, indent=2)}")
    return alert


def get_recent_alerts(limit=20):
    return list(recent_alerts)[:limit]
