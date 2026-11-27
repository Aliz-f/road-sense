# HISTORICAL VPS-ERA OPTION — not rendered or applied by current tooling.
# for a project LoadBalancer ingress IP and explicit owner deployment approval.
# CSC documents Routes as HTTP(S)-only; MQTT must not use an OpenShift Route.
apiVersion: v1
kind: Service
metadata:
  name: mqtt-broker-external
spec:
  type: LoadBalancer
  allocateLoadBalancerNodePorts: false
  externalTrafficPolicy: Local
  selector: {app: roadsense-mqtt-broker}
  ports:
    - {name: mqtt-tls, protocol: TCP, port: 30883, targetPort: mqtt-tls}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: roadsense-mqtt-ingress
spec:
  podSelector:
    matchLabels: {app: roadsense-mqtt-broker}
  policyTypes: [Ingress]
  ingress:
    - from:
        - ipBlock: {cidr: "${VPS_EGRESS_CIDR}"}
      ports:
        - {protocol: TCP, port: 8883}
    - from:
        - podSelector:
            matchExpressions:
              - {key: app, operator: In, values: [roadsense-processor, roadsense-analyzer]}
      ports:
        - {protocol: TCP, port: 8883}
