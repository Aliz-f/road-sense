# Apply only AFTER migration job roadsense-migrate-v1 completes.
apiVersion: apps/v1
kind: Deployment
metadata:
  name: signal-processor
spec:
  replicas: 1
  selector:
    matchLabels: {app: roadsense-processor}
  template:
    metadata:
      labels: {app: roadsense-processor}
    spec:
      containers:
        - name: processor
          image: ${PROCESSOR_IMAGE}
          imagePullPolicy: IfNotPresent
          envFrom:
            - configMapRef: {name: roadsense-settings}
          env:
            - name: MQTT_USERNAME
              valueFrom:
                secretKeyRef: {name: roadsense-mqtt-auth, key: username}
            - name: MQTT_PASSWORD
              valueFrom:
                secretKeyRef: {name: roadsense-mqtt-auth, key: password}
          volumeMounts:
            - {name: mqtt-ca, mountPath: /run/roadsense/mqtt, readOnly: true}
            - {name: tmp, mountPath: /tmp}
          resources:
            requests: {cpu: 50m, memory: 128Mi}
            limits: {cpu: 500m, memory: 512Mi}
          securityContext:
            runAsNonRoot: true
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
            capabilities: {drop: [ALL]}
            seccompProfile: {type: RuntimeDefault}
      volumes:
        - name: mqtt-ca
          secret:
            secretName: roadsense-mqtt-tls
            items:
              - {key: ca.crt, path: ca.crt}
        - name: tmp
          emptyDir: {medium: Memory, sizeLimit: 8Mi}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: road-analyzer
spec:
  replicas: 1
  selector:
    matchLabels: {app: roadsense-analyzer}
  template:
    metadata:
      labels: {app: roadsense-analyzer}
    spec:
      containers:
        - name: analyzer
          image: ${ANALYZER_IMAGE}
          imagePullPolicy: IfNotPresent
          envFrom:
            - configMapRef: {name: roadsense-settings}
          env:
            - name: MQTT_USERNAME
              valueFrom:
                secretKeyRef: {name: roadsense-mqtt-auth, key: username}
            - name: MQTT_PASSWORD
              valueFrom:
                secretKeyRef: {name: roadsense-mqtt-auth, key: password}
          volumeMounts:
            - {name: mqtt-ca, mountPath: /run/roadsense/mqtt, readOnly: true}
            - {name: db-auth, mountPath: /run/roadsense/postgres, readOnly: true}
            - {name: tmp, mountPath: /tmp}
          readinessProbe:
            exec:
              command: ["python", "-m", "road_analyzer.health"]
            initialDelaySeconds: 5
            periodSeconds: 10
          resources:
            requests: {cpu: 50m, memory: 128Mi}
            limits: {cpu: 500m, memory: 512Mi}
          securityContext:
            runAsNonRoot: true
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
            capabilities: {drop: [ALL]}
            seccompProfile: {type: RuntimeDefault}
      volumes:
        - name: mqtt-ca
          secret:
            secretName: roadsense-mqtt-tls
            items:
              - {key: ca.crt, path: ca.crt}
        - name: db-auth
          secret:
            secretName: roadsense-postgres-auth
            items:
              - {key: password, path: password}
        - name: tmp
          emptyDir: {medium: Memory, sizeLimit: 8Mi}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  replicas: 1
  selector:
    matchLabels: {app: roadsense-api}
  template:
    metadata:
      labels: {app: roadsense-api}
    spec:
      containers:
        - name: api
          image: ${API_IMAGE}
          imagePullPolicy: IfNotPresent
          ports:
            - {name: http, containerPort: 8000}
          envFrom:
            - configMapRef: {name: roadsense-settings}
          volumeMounts:
            - {name: db-auth, mountPath: /run/roadsense/postgres, readOnly: true}
            - {name: tmp, mountPath: /tmp}
          readinessProbe:
            httpGet: {path: /health/ready, port: http}
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet: {path: /health/live, port: http}
            initialDelaySeconds: 10
            periodSeconds: 20
          resources:
            requests: {cpu: 50m, memory: 128Mi}
            limits: {cpu: 500m, memory: 512Mi}
          securityContext:
            runAsNonRoot: true
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
            capabilities: {drop: [ALL]}
            seccompProfile: {type: RuntimeDefault}
      volumes:
        - name: db-auth
          secret:
            secretName: roadsense-postgres-auth
            items:
              - {key: password, path: password}
        - name: tmp
          emptyDir: {medium: Memory, sizeLimit: 8Mi}
---
apiVersion: v1
kind: Service
metadata:
  name: api
spec:
  type: ClusterIP
  selector: {app: roadsense-api}
  ports:
    - {name: http, port: 8000, targetPort: http}
