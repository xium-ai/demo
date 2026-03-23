# Makefile — XOS Demo (thin wrapper um tasks.nu)
# Voraussetzung: nushell installiert (brew install nushell)

.PHONY: infra app down reset status upload install-demo-db get-ca register install help

infra:           ; nu tasks.nu infra
app:             ; nu tasks.nu app
down:            ; nu tasks.nu down
reset:           ; nu tasks.nu reset
status:          ; nu tasks.nu status
upload:          ; nu tasks.nu upload
install-demo-db: ; nu tasks.nu install-demo-db
get-ca:          ; nu tasks.nu get-ca
register:        ; nu tasks.nu register
install:         ; nu tasks.nu install

# Interaktives Menü
menu:            ; nu tasks.nu

help:
	@echo ""
	@echo "  make infra     -- Phase 1: Vault + Keycloak + PostgreSQL + etcd"
	@echo "  make app       -- Phase 2: Anwendung (setzt Phase 1 voraus)"
	@echo "  make register  -- XOSP Fingerprint in etcd schreiben (einmalig)"
	@echo "  make status    -- Laufende Container"
	@echo "  make down      -- Stack stoppen"
	@echo "  make reset     -- Alles löschen inkl. Volumes"
	@echo "  make menu      -- Interaktives Menü"
	@echo ""
	@echo "  Oder direkt: nu tasks.nu"
	@echo ""
