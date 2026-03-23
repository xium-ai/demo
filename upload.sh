#!/bin/bash
# upload.sh — Lädt HTML Demo-Dateien in MinIO hoch.
#
# Dateien landen unter html/pages/... im Bucket — passend zum View-Pfad
# der Contexts (z.B. "html/pages/person/person.table.html").

set -e

MINIO_ALIAS="xos-dev"
MINIO_URL="http://localhost:9000"
MINIO_USER="xos-minio"
MINIO_PASS="xos-minio-bootstrap"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HTML_DIR="${XOS_HTML_DIR:-${SCRIPT_DIR}/demo/html}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[upload]${NC} $1"; }
warn() { echo -e "${YELLOW}[upload]${NC} $1"; }

if ! command -v mc &>/dev/null; then
    warn "mc nicht gefunden."
    warn "  Mac:   brew install minio/stable/mc"
    warn "  Linux: curl -sL https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc && chmod +x /usr/local/bin/mc"
    exit 1
fi

if [ ! -d "$HTML_DIR" ]; then
    warn "html/ nicht gefunden: $HTML_DIR"
    exit 1
fi

mc alias set ${MINIO_ALIAS} ${MINIO_URL} ${MINIO_USER} ${MINIO_PASS} --api S3v4 >/dev/null

# Parent-Verzeichnis als Quelle — so landet html/ als Prefix im Bucket.
# Contexts erwarten: html/pages/person/person.table.html
PARENT_DIR="$(dirname "${HTML_DIR}")"
HTML_NAME="$(basename "${HTML_DIR}")"

log "Uploade ${HTML_NAME}/ → xos-html/${HTML_NAME}/..."
mc mirror --overwrite --exclude "*.DS_Store" "${HTML_DIR}/" "${MINIO_ALIAS}/xos-html/${HTML_NAME}/"

echo ""
log "✅ Upload fertig"
log "   xos-html: $(mc ls --recursive ${MINIO_ALIAS}/xos-html | wc -l | tr -d ' ') Dateien"
