from __future__ import annotations

from typing import Any

import plotly.graph_objects as go


def vibration_figure(features: list[dict[str, Any]], events: list[dict[str, Any]]) -> go.Figure:
    figure = go.Figure()
    x = [item["source_start"] for item in features]
    figure.add_trace(go.Scatter(
        x=x, y=[item["vibration_rms_mg"] for item in features], mode="lines",
        name="Vibration RMS (mg)", line={"color": "#247ba0"},
    ))
    figure.add_trace(go.Scatter(
        x=x, y=[item["peak_deviation_mg"] for item in features], mode="lines",
        name="Peak deviation (mg)", line={"color": "#70c1b3"},
    ))
    if events:
        figure.add_trace(go.Scatter(
            x=[item["source_start"] for item in events],
            y=[item["observed_vibration_rms_mg"] for item in events],
            mode="markers", name="Exploratory high-vibration event",
            marker={"color": "#f25f5c", "size": 9, "symbol": "diamond"},
        ))
    figure.update_layout(
        xaxis_title="Source timestamp (UTC)", yaxis_title="Acceleration metric (mg)",
        hovermode="x unified", legend={"orientation": "h"}, margin={"l": 20, "r": 20, "t": 30, "b": 20},
    )
    return figure
