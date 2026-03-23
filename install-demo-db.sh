#!/bin/bash
# install-demo-db.sh -- Legt Demo-Tabellen an und befuellt sie mit Daten.
# Idempotent -- kann jederzeit wiederholt werden.

set -e

PG_USER="postgres"
PG_PASS="xos-pg-bootstrap"
PG_DB="xium"
SEED_SQL="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/demo/db/seed.sql"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[demo-db]${NC} $1"; }
warn() { echo -e "${YELLOW}[demo-db]${NC} $1"; }

if [ ! -f "$SEED_SQL" ]; then
    warn "seed.sql nicht gefunden: $SEED_SQL"
    exit 1
fi

log "Lade Demo-Daten in '$PG_DB'..."

docker exec -i xos-postgresql \
    sh -c "PGPASSWORD='$PG_PASS' psql -U $PG_USER -d $PG_DB" < "$SEED_SQL"

echo ""
log "✅ Demo-Daten geladen"
