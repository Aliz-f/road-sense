# MUHOS dataset profile — Phase 00

Inspection date: 2026-11-19. Scope: the five private archives in data/raw/archives. They were read in place; no archive or extracted recording is committed. RoadSense measures exploratory vehicle vibration, not potholes, road defects, or safety classes.

## Provenance, licence, and attribution

The source is the [MUHOS dataset specification](https://m3s-kuura.github.io/muhos-dataset/). It identifies the device as a Bosch XDK 110, located inside the car between the front seats, and says the data were collected around Oulu, Finland. The official page licenses MUHOS under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) and requires attribution to its paper plus a link to the dataset. Retain this attribution wherever derived data or demonstration material is published:

> B. Kämä et al., “Towards Collecting Large-Scale Vehicular Sensor Data for Open Access,” IEEE 23rd International Conference on Software Architecture Companion (ICSA-C), Amsterdam, 2026.

The local file names identify the recording categories. The official page lists approximate driving speeds of ~20 km/h (Bumpy gravel), 60 km/h (Paved road 60kmh), and 100 km/h (Highway). These are provenance labels, not vibration or safety ground truth.

## Archive inventory

| Local archive | Bytes | SHA-256 | Relevant member | Member bytes |
|---|---:|---|---|---:|
| Bumpy Gravel - imu.tar | 48,640,000 | 91d37ad4de7106d5038ed7bffe1e373db65e0f4771865da8975a216e76ed34f3 | imu/bosch_imu.csv | 4,394,591 |
| Paved Road 60kmh - imu.tar | 37,601,280 | cf3d0002573f1ecaa021034a3a20dee6cbb21a47989026d8b4ed0c8a81b7c6a4 | imu/bosch_imu.csv | 3,210,963 |
| Highway - imu.tar | 25,866,240 | d80eb161b896819851ed2d3aeea38da977c98a836096b31d9f6a5e8af193c903 | imu/bosch.csv | 2,294,580 |
| Bumpy Gravel - can.tar | 177,653,760 | e226a142aa81fa19184613d864210e5df2c46def6a6d5ea73a0c96497f425017 | can/toyota_CAN_20261019_085132.json | 92,056,951 |
| Paved Road 60kmh - can.tar | 149,852,160 | b3a31ed299b354eb3123642cda70b9a725329cf8b81b9ed9a1614b6f40c9453c | can/toyota_CAN_60kmtie.json | 76,305,517 |

The IMU archives also contain Multisense and lidar-IMU JSON members. Phase 00 inspected only the Bosch CSV member selected for RoadSense.

## Bosch CSV data dictionary

All three CSV files have this exact header:

    timestamp,acc_x_mg,acc_y_mg,acc_z_mg,mag_x_uT,mag_y_uT,mag_z_uT,mag_r_uT,gyro_x_mdeg,gyro_y_mdeg,gyro_z_mdeg

| Fields | Observed type and unit | Handling |
|---|---|---|
| timestamp | UTC RFC 3339 with Z; millisecond precision | Preserve as source timestamp, never replay time. |
| acc_x_mg, acc_y_mg, acc_z_mg | signed integer, mg | Selected vibration input axes. |
| mag_x_uT, mag_y_uT, mag_z_uT, mag_r_uT | signed integer, uT according to header | Preserve only as optional raw metadata in v1. |
| gyro_x_mdeg, gyro_y_mdeg, gyro_z_mdeg | signed integer, mdeg according to header | Preserve only as optional raw metadata in v1. |

The inspected official material does not provide an axis-to-vehicle coordinate transform. Mean acc_z_mg is near +1 g in every recording, but this does not establish a calibrated vertical axis. Orientation is **unknown**. Processing must use documented orientation-robust or per-session-baseline handling and must not label z as vertical.

## Measured IMU summary

Every Bosch CSV row was measured. “p50 interval” is the median positive adjacent timestamp interval; rate is its reciprocal. A gap is an interval greater than 1.5 × p50 (18 ms).

| Session ID | Rows | UTC start → end | Duration (s) | Interval ms min / p50 / p95 / max | Rate | Blank / duplicate / non-increasing / gaps |
|---|---:|---|---:|---|---:|---|
| bumpy-gravel-20261019 | 62,169 | 2026-10-19T05:51:57.052Z → 2026-10-19T06:04:23.585Z | 746.533 | 7 / 12 / 13 / 17 | 83.333 Hz | 0 / 0 / 0 / 0 |
| paved-road-60kmh-20261007 | 48,363 | 2026-10-07T09:52:42.239Z → 2026-10-07T10:02:22.696Z | 580.457 | 8 / 12 / 13 / 16 | 83.333 Hz | 0 / 0 / 0 / 0 |
| highway-20261007 | 34,195 | 2026-10-07T10:19:32.241Z → 2026-10-07T10:26:22.648Z | 410.407 | 9 / 12 / 13 / 15 | 83.333 Hz | 0 / 0 / 0 / 0 |

Observed acceleration min / arithmetic mean / max, in mg:

| Session | acc_x_mg | acc_y_mg | acc_z_mg |
|---|---|---|---|
| Bumpy gravel | -979 / 55.966 / 746 | -1265 / 25.092 / 993 | -43 / 1041.839 / 1999 |
| Paved road 60kmh | -468 / -35.555 / 406 | -711 / 42.542 / 877 | 660 / 1044.201 / 1591 |
| Highway | -474 / -27.406 / 383 | -533 / 29.359 / 606 | 600 / 1046.445 / 1495 |

An aggregate-only visual summary is committed at [muhos-imu-summary.svg](assets/muhos-imu-summary.svg); it contains no raw samples.

### Missing-data policy

1. Require the exact v1 header and a parseable UTC timestamp; reject a file with missing, non-numeric, or unknown-unit acceleration fields.
2. Preserve source order and assign replay sample_index from that order. Never fabricate timestamps or interpolate samples.
3. Flag non-increasing time and an adjacent positive interval greater than 18 ms. Windowing must not silently span a flagged discontinuity.
4. Retain the archive hash and member path in session provenance.

## CAN review (not MVP input)

Each CAN JSON item has timestamp, frame_id, message, signal, and value. The official specification calls these decoded known CAN signals, but provides no unit for SPEED; neither do the supplied JSON records. Numerical SPEED values must not be interpreted as km/h, m/s, or any other unit in RoadSense.

| Session | CAN records | Entire CAN UTC range, assuming numeric timestamp is Unix UTC | SPEED records | SPEED min / mean / max (unit unknown) | SPEED p50 interval |
|---|---:|---|---:|---|---:|
| Bumpy gravel | 555,741 | 2026-10-19T05:51:32.870950Z → 2026-10-19T06:04:20.203096Z | 29,744 | 0 / 16.268 / 42.12 | 0.025824 s |
| Paved road 60kmh | 460,399 | 2026-10-07T09:51:43.799234Z → 2026-10-07T10:02:39.881197Z | 24,505 | 0 / 28.598 / 60.36 | 0.026000 s |

The Unix-UTC interpretation produces 743.151096 s Bumpy-gravel IMU/CAN overlap and the full 580.457 s Paved-road IMU duration. Bumpy CAN ends 3.381904 s before its IMU; Paved CAN begins 58.439766 s before its IMU and ends 17.185197 s after it. Align by actual timestamps, never row number or recording start. This shows only temporal overlap, not clock-synchronisation accuracy or SPEED units.

## MVP and reproducibility

The MVP source is bumpy-gravel-20261019 / imu/bosch_imu.csv: it is the longest inspected Bosch recording, has the verified schema and clean timestamp sequence, and has a demonstration road-category label. The 60 km/h paved recording is the first comparison source after the IMU-only pipeline works. Highway is an additional test source. CAN is post-MVP pending SPEED-unit confirmation.

Regenerate the local-only JSON profile and aggregate SVG without installing packages:

    python3 tools/inspect_muhos.py --archives data/raw/archives \
      --output /tmp/roadsense-muhos-profile.json \
      --plot docs/assets/muhos-imu-summary.svg
    python3 -m json.tool /tmp/roadsense-muhos-profile.json >/dev/null

The script uses only the Python standard library, reads CSVs directly from tar archives, and writes no extracted recordings.

### Phase 00 validation evidence

The final checks were run on 2026-11-19 with these commands (outputs remain in
`/tmp`, except the already documented aggregate SVG):

    python3 -m py_compile tools/inspect_muhos.py
    python3 tools/inspect_muhos.py --archives data/raw/archives \
      --output /tmp/roadsense-muhos-profile-validate.json \
      --plot /tmp/muhos-imu-summary-validate.svg
    python3 -m json.tool /tmp/roadsense-muhos-profile-validate.json >/dev/null
    cmp docs/assets/muhos-imu-summary.svg /tmp/muhos-imu-summary-validate.svg
    git diff --check
    git check-ignore data/raw/archives/'Bumpy Gravel - imu.tar'

Assertions also rechecked the three row counts/time bounds, zero missing cells,
12 ms median interval, zero duplicates/non-increasing intervals/gaps, CAN SPEED
record counts, unverified SPEED unit marker, and SVG XML parsing. Sanitized
result: `profile assertions: PASS`; `Phase 00 validation: PASS`. `git ls-files
data/raw` returned no tracked raw files, and no service or infrastructure paths
were changed.

## Course and environment check

The official [Final-Project README](https://gitlab.com/sdx-oulu/2024/hw-and-project/-/blob/main/Final-Project/README.md) was retrieved on 2026-11-19. Requirements checked in this phase:

- A dockerized application that can interact with Rahti resources.
- Multiple interacting microservices demonstrated locally and in Rahti; backend interaction is emphasised over frontend polish.
- Submission material in the course repository Final-Project directory; open-source.url if applicable; a replacement architecture image; and a commit/push from that directory.
- A roughly 10-minute, maximum 10-minute video link with mic and camera, full-name introduction, project explanation, and commands proving the whole implementation.

This GitHub repository remains the development source. Phase 07 must verify the separate GitLab Final-Project hand-in layout and video requirements before submission. No deadline, rubric, or deployment permission was inferred beyond the retrieved README.

Read-only local prerequisite check: 146 GiB free workspace storage, 16 logical CPUs, and 15 GiB currently available RAM. Docker CLI 27.5.1 and Docker Compose v5.6.1 are installed, but this session could not connect to the Docker daemon socket, so daemon availability is **not** verified. No packages, Docker settings, VPS/Rahti system, or deployment were changed.

The topology remains: all services run locally via Docker Compose in Phases 01–05; only Phase 06 may use the personal VPS and CSC Rahti.
