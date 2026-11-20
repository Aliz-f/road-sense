# ONE-TIME job, apply after PostgreSQL + Mosquitto are healthy.
apiVersion: batch/v1
kind: Job
metadata:
  name: roadsense-migrate-v1
spec:
  ttlSecondsAfterFinished: 86400
  backoffLimit: 2
  template:
    metadata:
      labels: {app: roadsense-migrate}
    spec:
      restartPolicy: Never
      containers:
        - name: migrate
          image: ${ANALYZER_IMAGE}
          command: ["python", "-m", "road_analyzer.migrate"]
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
          resources:
            requests: {cpu: 50m, memory: 128Mi}
            limits: {cpu: 300m, memory: 256Mi}
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
