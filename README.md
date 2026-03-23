# Xium OS — Demo Stack

> ⚠️ **Hinweis für Administratoren**
>
> Diese Demo-Umgebung dient ausschließlich dazu, die **Funktionsfähigkeit von Xium OS** zu demonstrieren.
> Sie wurde **bewusst einfach gehalten** — das gilt insbesondere für die Sicherheitskonfiguration:
> Passwörter sind hartcodiert, Vault läuft im Dev-Modus, TLS ist nicht durchgängig aktiviert.
>
> **Diese Konfiguration ist nicht für den produktiven Einsatz geeignet.**
> Für eine produktionsreife Deploymentanleitung: [docs.xium.ai](https://docs.xium.ai)

Docker Compose Stack für die XOS Demo-Umgebung.

## Voraussetzungen

- Docker mit Docker Compose v2
- [Nushell](https://www.nushell.sh/) — für das interaktive Menü und `nu tasks.nu`
  ```bash
  # macOS
  brew install nushell

  # Linux
  cargo install nu
  # oder: https://github.com/nushell/nushell/releases
  ```
- [MinIO Client `mc`](https://min.io/docs/minio/linux/reference/minio-mc.html) — für HTML-Upload
  ```bash
  # macOS
  brew install minio/stable/mc

  # Linux
  curl -sL https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc && chmod +x /usr/local/bin/mc
  ```
- XOS Binaries — [Download von GitHub Releases](https://github.com/xium-ai/releases/releases/latest)
  - `xos` — Desktop Client
  - `xoso` — Context Importer (XML → Graph)
  - `xosb` — MCP Bridge (für Claude Desktop)

---

## Schnellstart

### Option A — Interaktives Menü (empfohlen)

```bash
nu tasks.nu
```

Navigiere mit den Pfeiltasten durch das Menü:

```
XOS Demo — Was soll ich tun?:
> Phase 1 — Vault, Keycloak, PostgreSQL, etcd starten
  Phase 2 — Anwendung starten (setzt infra voraus)
  XOSP Fingerprint in etcd schreiben (einmalig)
  ...
```

### Option B — Make Befehle

```bash
# Phase 1: Infrastruktur starten
make infra

# Warten bis Vault + Keycloak bereit (~30s), dann:

# Phase 2: Anwendung starten
make app

# XOSP Fingerprint registrieren (einmalig nach erstem Start)
make register
```

---

## Context-Daten laden (xoso)

Die XML Context-Definitionen müssen einmalig in den Memgraph-Graphen importiert werden:

```bash
# Beispiel: ctx/ Verzeichnis importieren
xoso import --uri "bolt://memgraph:xos-memgraph-bootstrap@localhost:7687" ./demo/ctx/
```

Alle `.ctx.xml` Dateien im Verzeichnis werden in den Graph geladen.
Nach `make reset` muss dieser Schritt wiederholt werden.

---

## XOS starten

```bash
xos --etcd localhost:2379
```

XOS verbindet sich mit etcd, holt die Konfiguration und öffnet den Browser.

**Login:**
| Benutzer | Passwort |
|---|---|
| `frank` | `xos-dev-2026` |
| `tristan` | `xos-dev-2026` |

---

## Claude Desktop — MCP Bridge (xosb)

Um XOS über Claude Desktop per stdio anzusprechen, `xosb` in die Claude Desktop Konfiguration eintragen:

**`~/Library/Application Support/Claude/claude_desktop_config.json`:**

```json
{
  "mcpServers": {
    "xos": {
      "command": "/pfad/zu/xosb",
      "args": ["--url", "https://localhost:59124/mcp"]
    }
  }
}
```

`xosb` fungiert als stdio↔HTTP Bridge zwischen Claude Desktop und dem laufenden XOS.
XOS muss gestartet sein bevor Claude Desktop die Bridge nutzen kann.

> **Hinweis:** Jede neue Claude-Chat-Session startet die Bridge neu —
> `oos_ast` (bzw. `xos_ast`) muss daher am Anfang jeder Session einmal aufgerufen werden.

---

## Endpunkte

| Service | URL | Zugangsdaten |
|---|---|---|
| Keycloak | http://keycloak.127.0.0.1.nip.io:8080/admin | `admin` / `xos-kc-bootstrap` |
| OpenBao (Vault) | http://openbao.127.0.0.1.nip.io:8200/ui | Token: `xos-dev-root-token` |
| MinIO Console | http://localhost:9001 | `xos-minio` / `xos-minio-bootstrap` |
| Memgraph Lab | http://localhost:3000 | — |
| etcd | http://localhost:2379 | — |
| XOSP | https://localhost:9100 | — |

---

## Make Befehle

| Befehl | Beschreibung |
|---|---|
| `make infra` | Phase 1: Vault, Keycloak, PostgreSQL, etcd |
| `make app` | Phase 2: XOSP, MinIO, Memgraph, Setup-Job |
| `make register` | XOSP Fingerprint in etcd schreiben (einmalig) |
| `make upload` | HTML-Templates nach MinIO hochladen |
| `make install-demo-db` | Demo-Daten in PostgreSQL laden |
| `make get-ca` | OpenBao CA-Zertifikat holen → `xos-ca.pem` |
| `make status` | Laufende Container anzeigen |
| `make down` | Stack stoppen |
| `make reset` | Stack + Volumes löschen |

Oder alles über das interaktive Menü: `nu tasks.nu`

---

## Stack-Komponenten

| Komponente | Port | Beschreibung |
|---|---|---|
| OpenBao | 8200 | Secrets, PKI, XOSP Identity |
| Keycloak | 8080 | IAM / OIDC |
| PostgreSQL | 5432 | Relationale Datenbank |
| etcd | 2379 | Konfigurationsquelle |
| MinIO | 9000 / 9001 | HTML-Templates (S3) |
| Memgraph | 7687 | Graph-Datenbank für Contexts |
| Redis | 6379 | Cache |
| LiveKit | 7880 | Voice / Video |
| XOSP | 9100 | Plugin-Server (`ghcr.io/xium-ai/xosp`) |

---

## make register — wann nötig?

`make register` liest den XOSP Fingerprint aus Vault und schreibt ihn in etcd.
Ausführen nach:
- Erstem `make app`
- `make reset` (neues Vault-Volume → neuer Fingerprint)

Solange das Vault-Volume erhalten bleibt (`make down` / `make app`), bleibt der Fingerprint konstant.
