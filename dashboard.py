"""
dashboard.py
------------
Dark, control-room-style live dashboard. Polls fastapi_app.py's /live
endpoint every 2 seconds. Run AFTER fastapi_app.py is running.
"""

import requests
from dash import Dash, dcc, html, Input, Output
import plotly.graph_objects as go

API_BASE = "http://localhost:8000"

DARK_BG = "#0d1117"
PANEL_BG = "#161b22"
TEXT = "#c9d1d9"
GREEN = "#3fb950"
RED = "#f85149"
AMBER = "#d29922"

app = Dash(__name__)
app.title = "ArcSense — Live Feeder Monitor"

app.layout = html.Div(
    style={"backgroundColor": DARK_BG, "color": TEXT, "fontFamily": "monospace",
           "minHeight": "100vh", "padding": "20px"},
    children=[
        html.H1("⚡ ArcSense — Live LT Feeder Monitor",
                style={"color": GREEN, "borderBottom": f"2px solid {PANEL_BG}", "paddingBottom": "10px"}),

        html.Div(id="connection-status", style={"marginBottom": "15px", "fontSize": "14px"}),

        html.Div(style={"display": "flex", "gap": "20px", "flexWrap": "wrap"}, children=[
            html.Div(id="node-cards", style={"flex": "1", "minWidth": "300px"}),
            html.Div(style={"flex": "2", "minWidth": "400px"}, children=[
                html.H3("Recent Events", style={"color": TEXT}),
                html.Div(id="event-log"),
            ]),
            html.Div(style={"flex": "2", "minWidth": "400px"}, children=[
                html.H3("Disaster Alert Feed (CAP format → NDMA SACHET)", style={"color": AMBER}),
                html.Div(id="alert-log"),
            ]),
        ]),

        dcc.Interval(id="poll-interval", interval=2000, n_intervals=0),
    ],
)


def node_card(node_id, info):
    is_isolated = info["status"] == "isolated"
    color = RED if is_isolated else GREEN
    label = "ISOLATED (breaker open)" if is_isolated else "LIVE"
    return html.Div(
        style={"backgroundColor": PANEL_BG, "border": f"1px solid {color}", "borderRadius": "6px",
               "padding": "12px", "marginBottom": "10px"},
        children=[
            html.Div(node_id, style={"fontWeight": "bold"}),
            html.Div(label, style={"color": color, "fontSize": "13px"}),
            html.Div(f"last: {info.get('last_prediction', '-')}", style={"fontSize": "12px", "opacity": 0.7}),
        ],
    )


def event_row(evt):
    is_break = evt.get("prediction") == "line_break"
    color = RED if is_break else TEXT
    return html.Div(
        f"{evt.get('timestamp', '')[:19]}  |  {evt.get('node_id', '?')}  |  {evt.get('prediction', '?')}"
        f"  (conf {evt.get('confidence', 0):.2f})",
        style={"color": color, "fontSize": "13px", "padding": "4px 0",
               "borderBottom": f"1px solid {PANEL_BG}"},
    )


def alert_row(alert):
    info = alert.get("info", {})
    return html.Div(
        style={"backgroundColor": PANEL_BG, "border": f"1px solid {AMBER}", "borderRadius": "4px",
               "padding": "8px", "marginBottom": "6px", "fontSize": "12px"},
        children=[
            html.Div(info.get("headline", "Alert"), style={"color": AMBER, "fontWeight": "bold"}),
            html.Div(f"severity: {info.get('severity', '-')}  |  urgency: {info.get('urgency', '-')}",
                     style={"opacity": 0.8}),
            html.Div(alert.get("sent", "")[:19], style={"opacity": 0.6, "fontSize": "11px"}),
        ],
    )


@app.callback(
    Output("node-cards", "children"),
    Output("event-log", "children"),
    Output("alert-log", "children"),
    Output("connection-status", "children"),
    Input("poll-interval", "n_intervals"),
)
def update(_n):
    try:
        data = requests.get(f"{API_BASE}/live", timeout=2).json()
    except Exception:
        return (html.Div("No data", style={"color": AMBER}),
                html.Div("No data", style={"color": AMBER}),
                html.Div("No data", style={"color": AMBER}),
                html.Div("⚠ API unreachable — is fastapi_app.py running on port 8000?", style={"color": RED}))

    cards = [node_card(nid, info) for nid, info in data.get("nodes", {}).items()]
    events = [event_row(e) for e in data.get("recent_predictions", [])[:15]]
    alerts = [alert_row(a) for a in data.get("recent_disaster_alerts", [])[:10]]
    if not alerts:
        alerts = [html.Div("No disaster alerts yet — system is quiet.", style={"opacity": 0.5, "fontSize": "13px"})]
    mqtt_state = "MQTT broker connected" if data.get("mqtt_connected") else "MQTT broker offline — using local event bus (demo-safe)"
    status = html.Div(f"● {mqtt_state}", style={"color": GREEN if data.get("mqtt_connected") else AMBER})

    return cards, events, alerts, status


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)
