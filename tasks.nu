#!/usr/bin/env nu
# tasks.nu — XOS Demo Task Runner
# Verwendung:  nu tasks.nu                                    -> interaktives Menü
#              nu tasks.nu infra                              -> direkt ausführen
#              XOS_NIP_BASE=192.168.1.140.nip.io nu tasks.nu -> Remote-Betrieb

const MINIO_ALIAS = "xos-dev"
const MINIO_USER  = "xos-minio"
const MINIO_PASS  = "xos-minio-bootstrap"
const VAULT_URL   = "http://localhost:8200"
const VAULT_TOKEN = "xos-dev-root-token"
const MINIO_URL   = "http://localhost:9000"
const ETCD_URL    = "http://localhost:2379"
const ETCD_KEY    = "/xos/services/xosp/fp"
const PG_USER     = "postgres"
const PG_PASS     = "xos-pg-bootstrap"
const PG_DB       = "xium"

# NIP_BASE aus Env-Variable lesen -- Default: lokal
def nip-base [] {
    $env | get -o XOS_NIP_BASE | default "127.0.0.1.nip.io"
}

# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def log [msg: string] {
    print $"(ansi green)[xos](ansi reset) ($msg)"
}

def warn [msg: string] {
    print $"(ansi yellow)[xos](ansi reset) ($msg)"
}

def ok [msg: string] {
    print $"✅ ($msg)"
}

def fail [msg: string] {
    print $"❌ ($msg)"
    exit 1
}

# Verzeichnis in dem tasks.nu liegt — Basis für alle relativen Pfade
def script-dir [] {
    $env.CURRENT_FILE | path dirname
}

# docker compose Args als Liste zusammenbauen und extern ausführen
def dc [args: list<string>] {
    let base = ["compose" "--project-name" "xos" "--project-directory" (script-dir)]
    run-external "docker" ...($base ++ $args)
}

# ── Phase 1: Infrastruktur ────────────────────────────────────────────────────

def "main infra" [] {
    log "Starte Infrastruktur..."
    dc ["--profile" "infra" "up" "-d"]
    print ""
    ok "Infrastruktur gestartet"
    print $"  Vault:    http://openbao.(nip-base):8200/ui  \(Token: xos-dev-root-token\)"
    print $"  Keycloak: http://keycloak.(nip-base):8080/admin  \(admin / xos-kc-bootstrap\)"
    print ""
    print "-> Wenn Vault + Keycloak bereit: nu tasks.nu app"
}

# ── Phase 2: Anwendung ────────────────────────────────────────────────────────

def "main app" [] {
    log "Starte Anwendung..."
    dc ["--profile" "app" "up" "-d" "--build"]
    print ""
    log "Warte auf setup-Job..."
    run-external "docker" "wait" "xos-setup"
    print ""
    main upload
    main install-demo-db
    main get-ca
    print ""
    print "====================================="
    ok "XOS Demo gestartet"
    print "====================================="
    print "  MinIO:  http://localhost:9001"
    print $"  XOSP:   https://localhost:9100"
    print "  Login:  frank / xos-dev-2026"
}

# ── Stack steuern ─────────────────────────────────────────────────────────────

def "main down" [] {
    log "Stoppe Stack..."
    dc ["--profile" "infra" "--profile" "app" "down"]
    ok "Stack gestoppt"
}

def "main reset" [] {
    log "Lösche Stack + Volumes..."
    dc ["--profile" "infra" "--profile" "app" "down" "-v" "--remove-orphans"]
    rm -f ([$"(script-dir)" "xos-ca.pem"] | path join)
    ok "Stack + Volumes gelöscht"
}

def "main status" [] {
    dc ["--profile" "infra" "--profile" "app" "ps"]
}

# ── MinIO Upload ──────────────────────────────────────────────────────────────

def "main upload" [] {
    let html_dir = $env | get -o XOS_HTML_DIR | default $"(script-dir)/demo/html"

    if not ($html_dir | path exists) {
        fail $"html/ nicht gefunden: ($html_dir)"
    }

    if (which mc | is-empty) {
        warn "mc nicht gefunden."
        warn "  Mac:   brew install minio/stable/mc"
        warn "  Linux: curl -sL https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc && chmod +x /usr/local/bin/mc"
        exit 1
    }

    run-external "mc" "alias" "set" $MINIO_ALIAS $MINIO_URL $MINIO_USER $MINIO_PASS "--api" "S3v4" | ignore
    log $"Uploade html/ → xos-html/html/..."
    run-external "mc" "mirror" "--overwrite" "--exclude" "*.DS_Store" $"($html_dir)/" $"($MINIO_ALIAS)/xos-html/html/"

    let count = (run-external "mc" "ls" "--recursive" $"($MINIO_ALIAS)/xos-html" | lines | length)
    print ""
    ok $"Upload fertig — ($count) Dateien"
}

# ── Demo-Datenbank ────────────────────────────────────────────────────────────

def "main install-demo-db" [] {
    let seed = ([$"(script-dir)" "demo" "db" "seed.sql"] | path join)

    if not ($seed | path exists) {
        fail $"seed.sql nicht gefunden: ($seed)"
    }

    log $"Lade Demo-Daten in '($PG_DB)'..."
    open $seed | run-external "docker" "exec" "-i" "xos-postgresql" "sh" "-c" $"PGPASSWORD='($PG_PASS)' psql -U ($PG_USER) -d ($PG_DB)"
    ok "Demo-Daten geladen"
}

# ── CA-Zertifikat holen ───────────────────────────────────────────────────────

def "main get-ca" [] {
    let ca_path = ([$"(script-dir)" "xos-ca.pem"] | path join)
    rm -f $ca_path

    let result = (http get --headers [X-Vault-Token $VAULT_TOKEN] $"($VAULT_URL)/v1/pki/ca/pem")
    $result | save $ca_path
    ok "xos-ca.pem"
}

# ── XOSP Fingerprint registrieren ─────────────────────────────────────────────

def "main register" [] {
    log "Lese XOSP Fingerprint aus Vault..."

    let resp = (http get --headers [X-Vault-Token $VAULT_TOKEN] $"($VAULT_URL)/v1/secret/data/xosp/identity")
    let fp = $resp.data.data.fingerprint

    print $"   Fingerprint: ($fp | str substring 0..16)..."
    log $"Schreibe in etcd: ($ETCD_KEY)"

    let key_b64   = ($ETCD_KEY | encode base64)
    let value_b64 = ($fp | encode base64)

    (http post --content-type application/json $"($ETCD_URL)/v3/kv/put" {key: $key_b64, value: $value_b64}) | ignore

    ok "Fingerprint registriert — XOS neu starten"
}

# ── Interaktives Menü ─────────────────────────────────────────────────────────

def "main" [] {
    let tasks = [
        {value: "infra",           description: "Phase 1 — Vault, Keycloak, PostgreSQL, etcd starten"},
        {value: "app",             description: "Phase 2 — Anwendung starten (setzt infra voraus)"},
        {value: "register",        description: "XOSP Fingerprint in etcd schreiben (einmalig)"},
        {value: "status",          description: "Laufende Container anzeigen"},
        {value: "upload",          description: "HTML-Dateien nach MinIO spiegeln"},
        {value: "install-demo-db", description: "Demo-Daten in PostgreSQL laden"},
        {value: "get-ca",          description: "CA-Zertifikat aus Vault holen"},
        {value: "down",            description: "Stack stoppen"},
        {value: "reset",           description: "Stack + Volumes löschen"},
    ]

    let choice = try {
        $tasks | input list --display description "XOS Demo — Was soll ich tun?"
    } catch {
        return
    }

    match $choice.value {
        "infra"           => { main infra },
        "app"             => { main app },
        "register"        => { main register },
        "status"          => { main status },
        "upload"          => { main upload },
        "install-demo-db" => { main install-demo-db },
        "get-ca"          => { main get-ca },
        "down"            => { main down },
        "reset"           => { main reset },
        _                 => { warn "Unbekannte Auswahl" }
    }
}
