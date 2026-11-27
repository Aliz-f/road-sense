from __future__ import annotations

import os

import requests
import streamlit as st

from roadsense_dashboard.charts import vibration_figure
from roadsense_dashboard.client import ApiClient


LIMITATION = (
    "RoadSense reports exploratory vehicle-vibration metrics. Events are threshold observations, "
    "not scientifically validated potholes, road defects, comfort ratings, or safety classifications. "
    "Sensor orientation and mounting effects are not calibrated."
)


def main() -> None:
    st.set_page_config(page_title="RoadSense", page_icon="🚗", layout="wide")
    st.title("RoadSense vehicle-vibration explorer")
    # st.warning(LIMITATION)
    client = ApiClient(os.environ.get("API_INTERNAL_URL", "http://api:8000"))

    try:
        system_status = client.status()
        sessions = client.sessions()
    except (requests.RequestException, ValueError, KeyError) as error:
        st.error(f"RoadSense API is unavailable: {error}")
        st.stop()

    columns = st.columns(4)
    columns[0].metric("Observed runs", system_status["run_count"])
    columns[1].metric("Feature windows", system_status["feature_count"])
    columns[2].metric("Vibration events", system_status["event_count"])
    columns[3].metric("Pending event publishes", system_status["pending_event_publications"])

    if not sessions:
        st.info("No recordings have been observed yet. Run the sensor replay to populate the dashboard.")
        return

    session_by_label = {
        f'{item["road_category"]} — {item["session_id"]}': item for item in sessions
    }
    selected_label = st.selectbox("Recording", list(session_by_label))
    selected_session = session_by_label[selected_label]
    try:
        runs = client.runs(selected_session["session_id"])
    except (requests.RequestException, ValueError, KeyError) as error:
        st.error(f"Could not load runs for the selected recording: {error}")
        return
    if not runs:
        st.info("This recording has no observed processing runs.")
        return

    run_by_label = {
        f'{item["source_start"]} — {item["run_id"]}': item for item in runs
    }
    selected_run_label = st.selectbox("Processing run", list(run_by_label))
    selected_run = run_by_label[selected_run_label]
    try:
        features = client.features(selected_run["run_id"])
        events = client.events(selected_run["run_id"])
    except (requests.RequestException, ValueError, KeyError) as error:
        st.error(f"Could not load the selected run: {error}")
        return

    st.caption(
        f'Status: {selected_run["status"]} · algorithm: {selected_run["algorithm_version"]} · '
        f'{len(features)} feature windows · {len(events)} events'
    )
    if features:
        st.plotly_chart(vibration_figure(features, events), use_container_width=True)
    else:
        st.info("The selected run has no feature windows.")

    st.subheader("Exploratory high-vibration events")
    if events:
        st.dataframe([{
            "source_start": item["source_start"],
            "window_index": item["window_index"],
            "observed_rms_mg": item["observed_vibration_rms_mg"],
            "threshold_rms_mg": item["threshold_vibration_rms_mg"],
            "quality_flags": ", ".join(item["quality_flags"]),
            "rule_version": item["rule_version"],
        } for item in events], use_container_width=True, hide_index=True)
    else:
        st.info("No threshold events were stored for this run.")

    with st.expander("Recording provenance and methodology"):
        st.json({
            "session_id": selected_session["session_id"],
            "sensor_id": selected_session["sensor_id"],
            "source_archive_sha256": selected_session["source_archive_sha256"],
            "source_member": selected_session["source_member"],
            "source_bounds": [selected_session["source_start"], selected_session["source_end"]],
            "row_count": selected_session["row_count"],
            "orientation_note": selected_session["orientation_note"],
        })
        st.write(
            "Each one-second source-time window uses acceleration-vector magnitude, subtracts the "
            "window median magnitude, and reports RMS and maximum absolute deviation in mg."
        )


if __name__ == "__main__":
    main()
