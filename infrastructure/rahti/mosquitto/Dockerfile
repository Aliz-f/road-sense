# OpenShift-compatible Mosquitto image; build and inspect before deployment.
FROM eclipse-mosquitto:2.0.22@sha256:81a6193ae693942a3231cd3ac52875b02b7e3a19da671b2fb4b55cc874c5b279
COPY infrastructure/rahti/mosquitto/mosquitto.conf /mosquitto/config/mosquitto.conf
# OpenShift restricted SCC can assign an arbitrary non-root UID, normally group 0.
USER 0
RUN chgrp -R 0 /mosquitto && chmod -R g=u /mosquitto
# Local image checks use a non-root UID in group 0. Rahti's restricted SCC
# replaces the UID and supplies its project fsGroup for mounted PVC access.
USER 10001:0
EXPOSE 8883
