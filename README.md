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
Kein Registry-Login erforderlich — alle Images sind öffentlich oder werden lokal gebaut.

## Voraussetzungen

- Docker mit Docker Compose v2
- [Nushell](https://www.nushell.sh/)
  ```bash
  # macOS
  brew install nushell

  # Linux
  # https://github.com/nushell/nushell/releases
  ```
- [MinIO Client `mc`](https://min.io/docs/minio/linux/reference/minio-mc.html) — für HTML-Upload
  ```bash
  # macOS
  brew install minio/stable/mc

  # Linux
  curl -sL https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc && chmod +x /usr/local/bin/mc
  ```
- XOS Binaries — per `install.sh` oder [manuell von GitHub Releases](https://github.com/xium-ai/releases/releases/latest)
  ```bash
  ./install.sh
  ```
  Installiert: `xos`, `xoso`, `xosb`

---

## Schnellstart

### Lokal (alles auf demselben Rechner)

```bash
# Phase 1: Infrastruktur starten
make infra

# Warten bis Vault + Keycloak bereit (~30s), dann:
make app

# XOS starten
./xos --etcd localhost:2379
```

### Remote (Stack läuft auf einem anderen Rechner)

Wenn der Demo-Stack auf einem anderen Rechner läuft (z.B. Server, VM), muss die
IP-Adresse dieses Rechners beim Start bekannt gemacht werden:

```bash
# Auf dem Server — Stack mit der eigenen IP starten
XOS_NIP_BASE=<SERVER-IP>.nip.io make reset
make infra
make app
```

```bash
# Auf dem Client-Rechner — XOS mit den Remote-Adressen starten
./xos --xosp-url https://<SERVER-IP>:9100 --etcd <SERVER-IP>:2379
```

Das CA-Zertifikat (`xos-ca.pem`) vom Server holen und dem System als
vertrauenswürdig hinzufügen, damit die TLS-Verbindung zu XOSP funktioniert.

---

## Login

| Benutzer | Passwort |
|---|---|
| `frank` | `xos-dev-2026` |
| `tristan` | `xos-dev-2026` |

---

## Claude Desktop — MCP Bridge (xosb)

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

> **Hinweis:** Jede neue Claude-Chat-Session startet die Bridge neu —
> `xos_ast` muss daher am Anfang jeder Session einmal aufgerufen werden.

---

## Endpunkte

| Service | URL | Zugangsdaten |
|---|---|---|
| Keycloak | http://localhost:8080/admin | `admin` / `xos-kc-bootstrap` |
| OpenBao (Vault) | http://localhost:8200/ui | Token: `xos-dev-root-token` |
| MinIO Console | http://localhost:9001 | `xos-minio` / `xos-minio-bootstrap` |
| Memgraph Lab | http://localhost:3000 | — |
| XOSP | https://localhost:9100 | — |

Bei Remote-Betrieb `localhost` durch die Server-IP ersetzen.

---

## Make Befehle

| Befehl | Beschreibung |
|---|---|
| `make infra` | Phase 1: Vault, Keycloak, PostgreSQL, etcd |
| `make app` | Phase 2: XOSP, MinIO, Memgraph, Setup-Job |
| `make upload` | HTML-Templates nach MinIO hochladen |
| `make install-demo-db` | Demo-Daten in PostgreSQL laden |
| `make get-ca` | OpenBao CA-Zertifikat holen → `xos-ca.pem` |
| `make status` | Laufende Container anzeigen |
| `make down` | Stack stoppen |
| `make reset` | Stack + Volumes löschen |

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
| XOSP | 9100 | Plugin-Server |
