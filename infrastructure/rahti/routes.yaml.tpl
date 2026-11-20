# OPTIONAL, EXTERNAL NETWORK ACCESS — NEVER APPLY WITHOUT EXPLICIT APPROVAL.
# Check route capabilities/hostname/TLS termination on your ACTUAL Rahti project.
# The API is not authenticated: the ingress allowlist is a required mitigation,
# and must be VERIFIED end-to-end or replaced by approved VPN/authenticated proxy.
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: roadsense-mqtt
  annotations:
    haproxy.router.openshift.io/ip_whitelist: "${VPS_EGRESS_CIDR}"
spec:
  host: ${MQTT_PUBLIC_HOST}
  to: {kind: Service, name: mqtt-broker}
  port: {targetPort: mqtt-tls}
  tls:
    termination: passthrough
    insecureEdgeTerminationPolicy: None
---
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: roadsense-api
  annotations:
    haproxy.router.openshift.io/ip_whitelist: "${VPS_EGRESS_CIDR}"
spec:
  host: ${API_PUBLIC_HOST}
  to: {kind: Service, name: api}
  port: {targetPort: http}
  tls:
    termination: edge
    insecureEdgeTerminationPolicy: Redirect
