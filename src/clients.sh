#!/bin/sh
# Task 2 — 4 client Pod (Phụ lục B2). Chạy: sh src/clients.sh  (sau khi source env.sh)
# owner/ingestor/analyst: nhãn access=s3 + Secret s3-<role>. blocked: không nhãn, không credentials.
# Khác bản PDF: dựng LABELS riêng để không sinh "{role: blocked, }" (dấu phẩy thừa).
set -eu
: "${NS:?}" "${CLIENT_IMAGE:?}"
for role in owner ingestor analyst blocked; do
  LABELS="{role: $role}"
  CREDS=""
  if [ "$role" != blocked ]; then
    LABELS="{role: $role, access: s3}"
    CREDS="envFrom: [{secretRef: {name: s3-$role}}]"
  fi
  cat <<YAML | kubectl -n "$NS" apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: $role
  labels: $LABELS
spec:
  automountServiceAccountToken: false
  securityContext: {runAsUser: 1000, runAsNonRoot: true}
  containers:
  - name: client
    image: $CLIENT_IMAGE
    command: [sleep, infinity]
    securityContext:
      allowPrivilegeEscalation: false
      capabilities: {drop: [ALL]}
      seccompProfile: {type: RuntimeDefault}
    resources:
      requests: {cpu: 100m, memory: 128Mi}
      limits: {cpu: 500m, memory: 512Mi}
    env:
    - {name: S3_ENDPOINT, value: 'http://objects:8333'}
    - {name: PRINCIPAL, value: '$role'}
    $CREDS
YAML
done
kubectl -n "$NS" wait --for=condition=Ready pod/owner pod/ingestor \
  pod/analyst pod/blocked --timeout=120s
