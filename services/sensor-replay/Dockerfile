# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e
FROM python:3.12.7-slim-bookworm@sha256:60d9996b6a8a3689d36db740b49f4327be3be09a21122bd02fb8895abb38b50d AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY services/sensor-replay/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY services/sensor-replay/src ./src

FROM base AS runtime
USER 10001:10001
ENTRYPOINT ["python", "-m", "sensor_replay"]

FROM base AS test
COPY services/sensor-replay/tests ./tests
USER 10001:10001
ENTRYPOINT ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]
