# Apply ONLY after secret creation and explicit Rahti deployment approval.
# Do not create public Routes as part of this baseline.
apiVersion: v1
kind: ConfigMap
metadata:
  name: roadsense-settings
data:
  MQTT_HOST: mqtt-broker
  MQTT_PORT: "8883"
  MQTT_TLS_CA_FILE: /run/roadsense/mqtt/ca.crt
  MQTT_RAW_TOPIC: roadsense/v1/imu/raw
  MQTT_RUN_COMPLETE_TOPIC: roadsense/v1/imu/run-complete
  MQTT_FEATURE_TOPIC: roadsense/v1/imu/features
  MQTT_EVENT_TOPIC: roadsense/v1/events
  PROCESSOR_MQTT_CLIENT_ID: roadsense-signal-processor-rahti
  ANALYZER_MQTT_CLIENT_ID: roadsense-road-analyzer-rahti
  PROCESSOR_QUEUE_CAPACITY: "1024"
  ANALYZER_QUEUE_CAPACITY: "1024"
  MQTT_CONNECT_TIMEOUT_SECONDS: "10"
  MQTT_PUBLISH_TIMEOUT_SECONDS: "10"
  ANALYZER_VIBRATION_RMS_THRESHOLD_MG: "100.0"
  ANALYZER_RULE_VERSION: roadsense-high-vibration-rms-v1-t100
  ANALYZER_SESSION_REGISTRY_FILE: /app/session-registry.json
  POSTGRES_HOST: postgres
  POSTGRES_PORT: "5432"
  POSTGRES_DB: roadsense
  POSTGRES_USER: roadsense
  POSTGRES_PASSWORD_FILE: /run/roadsense/postgres/password
  POSTGRES_CONNECT_TIMEOUT_SECONDS: "5"
  POSTGRES_CONNECT_RETRIES: "30"
  ANALYZER_READY_FILE: /tmp/road-analyzer-ready
  PROCESSOR_READY_FILE: /tmp/signal-processor-ready
  PROCESSOR_STATE_FILE: /var/lib/roadsense-processor/processor-state.sqlite3
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: roadsense-mqtt-acl
data:
  acl_file: |
    user roadsense-remote
    topic readwrite roadsense/v1/imu/raw
    topic readwrite roadsense/v1/imu/run-complete
    topic readwrite roadsense/v1/imu/features
    topic readwrite roadsense/v1/events
    topic read $SYS/#
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: roadsense-postgres-data
spec:
  accessModes: [ReadWriteOnce]
  # Storage class must be verified with: oc get storageclass
  resources:
    requests:
      storage: 5Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: roadsense-mqtt-data
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 1Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: roadsense-processor-state
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 1Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels: {app: roadsense-postgres}
  template:
    metadata:
      labels: {app: roadsense-postgres}
    spec:
      containers:
        - name: postgres
          image: ${POSTGRES_IMAGE}
          imagePullPolicy: IfNotPresent
          env:
            - name: POSTGRESQL_USER
              value: roadsense
            - name: POSTGRESQL_DATABASE
              value: roadsense
            - name: POSTGRESQL_PASSWORD
              valueFrom:
                secretKeyRef: {name: roadsense-postgres-auth, key: password}
          ports:
            - {name: postgres, containerPort: 5432}
          readinessProbe:
            exec:
              command: ["/bin/sh", "-ec", "pg_isready -U roadsense -d roadsense"]
            initialDelaySeconds: 8
            periodSeconds: 5
          resources:
            requests: {cpu: 200m, memory: 256Mi}
            limits: {cpu: "1", memory: 1Gi}
          securityContext:
            runAsNonRoot: true
            allowPrivilegeEscalation: false
            capabilities: {drop: [ALL]}
            seccompProfile: {type: Localhost, localhostProfile: rahti-custom-seccomp.json}
          volumeMounts:
            - {name: data, mountPath: /var/lib/pgsql/data}
      volumes:
        - name: data
          persistentVolumeClaim: {claimName: roadsense-postgres-data}
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
spec:
  type: ClusterIP
  selector: {app: roadsense-postgres}
  ports:
    - {name: postgres, port: 5432, targetPort: postgres}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: roadsense-postgres-private
spec:
  podSelector:
    matchLabels: {app: roadsense-postgres}
  policyTypes: [Ingress]
  ingress:
    - from:
        - podSelector:
            matchExpressions:
              - {key: app, operator: In, values: [roadsense-api, roadsense-analyzer, roadsense-migrate]}
      ports:
        - {protocol: TCP, port: 5432}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mqtt-broker
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels: {app: roadsense-mqtt-broker}
  template:
    metadata:
      labels: {app: roadsense-mqtt-broker}
    spec:
      # Required by CSC when externalTrafficPolicy=Local is used for the
      # separately approved MQTT LoadBalancer Service.
      nodeSelector:
        rahti.csc.fi/local-load-balancer: ""
      initContainers:
        - name: verify-mqtt-persistence-writable
          image: ${BROKER_IMAGE}
          command:
            - /bin/sh
            - -ec
            - 'probe=/mosquitto/data/.roadsense-write-test-$$; (umask 077 && : > "$probe") && rm -f "$probe"'
          resources:
            requests: {cpu: 10m, memory: 16Mi}
            limits: {cpu: 50m, memory: 32Mi}
          securityContext:
            runAsNonRoot: true
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
            capabilities: {drop: [ALL]}
            seccompProfile: {type: Localhost, localhostProfile: rahti-custom-seccomp.json}
          volumeMounts:
            - {name: data, mountPath: /mosquitto/data}
      containers:
        - name: broker
          image: ${BROKER_IMAGE}
          imagePullPolicy: IfNotPresent
          ports:
            - {name: mqtt-tls, containerPort: 8883}
          readinessProbe:
            tcpSocket: {port: mqtt-tls}
            initialDelaySeconds: 3
            periodSeconds: 5
          resources:
            requests: {cpu: 60m, memory: 96Mi}
            limits: {cpu: 300m, memory: 256Mi}
          securityContext:
            runAsNonRoot: true
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
            capabilities: {drop: [ALL]}
            seccompProfile: {type: Localhost, localhostProfile: rahti-custom-seccomp.json}
          volumeMounts:
            - {name: mqtt-runtime, mountPath: /run/roadsense/mqtt, readOnly: true}
            - {name: data, mountPath: /mosquitto/data}
            - {name: tmp, mountPath: /tmp}
      volumes:
        - name: mqtt-runtime
          projected:
            sources:
              - secret:
                  name: roadsense-mqtt-tls
                  items:
                    - {key: ca.crt, path: ca.crt}
                    - {key: server.crt, path: server.crt}
                    - {key: server.key, path: server.key}
              - secret:
                  name: roadsense-mqtt-auth
                  items:
                    - {key: password_file, path: password_file}
              - configMap:
                  name: roadsense-mqtt-acl
                  items:
                    - {key: acl_file, path: acl_file}
        - name: data
          persistentVolumeClaim: {claimName: roadsense-mqtt-data}
        - name: tmp
          emptyDir: {medium: Memory, sizeLimit: 8Mi}
---
apiVersion: v1
kind: Service
metadata:
  name: mqtt-broker
spec:
  type: ClusterIP
  selector: {app: roadsense-mqtt-broker}
  ports:
    - {name: mqtt-tls, port: 8883, targetPort: mqtt-tls}
