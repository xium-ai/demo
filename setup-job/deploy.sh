#!/bin/bash
# setup-job/deploy.sh — Deployt den XOS Setup Job im Cluster.
#
# Aufruf:
#   ./deploy.sh                                        # ohne Client IDs (nur Vault Mounts + MinIO)
#   ./deploy.sh <XOS_CLIENT_ID> <XOSP_CLIENT_ID>      # mit Client IDs (vollständig)
#
# Nach dem Authentik Setup:
#   kubectl exec ... -- ak shell < ../authentik-setup/authentik_setup.py
#   ./deploy.sh cuvvz33y... MZQLPYqV...

set -e

NAMESPACE="xos-dev"
XOS_CLIENT_ID="${1:-}"
XOSP_CLIENT_ID="${2:-}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[setup]${NC} $1"; }
warn() { echo -e "${YELLOW}[setup]${NC} $1"; }

# Alten Job löschen falls vorhanden
kubectl delete job xos-setup -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null

# Script als ConfigMap deployen
log "Deploye Setup Script als ConfigMap..."
kubectl create configmap xos-setup-script \
  --from-file=xos_setup.py=xos_setup.py \
  --namespace="$NAMESPACE" \
  --dry-run=client -o yaml | kubectl apply -f -

# Job mit Client IDs starten
log "Starte Setup Job..."
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: xos-setup
  namespace: ${NAMESPACE}
spec:
  ttlSecondsAfterFinished: 300
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: setup
        image: python:3.12-alpine
        imagePullPolicy: IfNotPresent
        command: ["python", "/scripts/xos_setup.py"]
        env:
        - name: XOS_CLIENT_ID
          value: "${XOS_CLIENT_ID}"
        - name: XOSP_CLIENT_ID
          value: "${XOSP_CLIENT_ID}"
        volumeMounts:
        - name: scripts
          mountPath: /scripts
      volumes:
      - name: scripts
        configMap:
          name: xos-setup-script
EOF

# Auf Abschluss warten und Logs anzeigen
log "Warte auf Job..."
kubectl wait --for=condition=complete job/xos-setup \
  -n "$NAMESPACE" --timeout=300s &
WAIT_PID=$!

# Logs parallel anzeigen
sleep 3
kubectl logs -f job/xos-setup -n "$NAMESPACE" 2>/dev/null &

wait $WAIT_PID
STATUS=$?

if [ $STATUS -eq 0 ]; then
  log "✅ Setup erfolgreich abgeschlossen"
else
  warn "⚠️  Setup fehlgeschlagen — Logs prüfen:"
  warn "  kubectl logs job/xos-setup -n ${NAMESPACE}"
  exit 1
fi
