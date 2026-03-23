# XOS Demo Stack

Docker Compose Stack für die XOS Demo-Umgebung.

## Voraussetzungen

- Docker mit Docker Compose v2
- `python3` (für `make register`)
- XOS Binary (`xos`) — [Download](https://github.com/xium-ai/releases)

## Schnellstart

```bash
# Phase 1: Infrastruktur
make infra

# Warten bis Vault + Keycloak bereit sind (~30s)

# Phase 2: Anwendung
make app

# XOSP Fingerprint registrieren (einmalig)
make register

# XOS starten
./xos --etcd localhost:2379
```

## Login

| | |
|---|---|
| Benutzer | `frank` / `tristan` |
| Passwort | `xos-dev-2026` |

## Endpunkte

| Service | URL | Zugangsdaten |
|---|---|---|
| Keycloak | http://keycloak.127.0.0.1.nip.io:8080/admin | `admin` / `xos-kc-bootstrap` |
| OpenBao (Vault) | http://openbao.127.0.0.1.nip.io:8200/ui | Token: `xos-dev-root-token` |
| MinIO Console | http://localhost:9001 | `xos-minio` / `xos-minio-bootstrap` |
| Memgraph Lab | http://localhost:3000 | — |
| etcd | http://localhost:2379 | — |
| XOSP | https://localhost:9100 | — |

## Makefile

| Befehl | Beschreibung |
|---|---|
| `make infra` | Phase 1: Vault, Keycloak, PostgreSQL, etcd |
| `make app` | Phase 2: XOSP, MinIO, Memgraph, Setup-Job |
| `make register` | XOSP Fingerprint in etcd schreiben (einmalig) |
| `make upload` | HTML-Templates nach MinIO hochladen |
| `make seed-ctx` | Context-Gruppen in Memgraph laden |
| `make install-ca` | OpenBao CA im Mac Keychain installieren (sudo) |
| `make status` | Laufende Container anzeigen |
| `make down` | Stack stoppen |
| `make reset` | Stack + Volumes löschen |

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

## make register — wann nötig?

`make register` liest den XOSP Fingerprint aus Vault und schreibt ihn in etcd.
Ausführen nach:
- Erstem `make app`
- `make reset` (neues Vault-Volume → neuer Fingerprint)

Solange das Vault-Volume erhalten bleibt (`make down` / `make app`), bleibt der Fingerprint konstant.
