#!/usr/bin/env python3
"""
register-xosp.py -- Liest XOSP Fingerprint aus Vault und schreibt ihn in etcd.

Einmalig nach 'make app' ausfuehren (oder nach XOSP-Neustart mit neuem Key).
Danach nutzt XOS Fingerprint-Pinning statt Vault CA.

Aufruf: python3 register-xosp.py
"""

import sys, json, base64, urllib.request, urllib.error

VAULT_URL   = "http://localhost:8200"
VAULT_TOKEN = "xos-dev-root-token"
ETCD_URL    = "http://localhost:2379"
ETCD_KEY    = "/xos/services/xosp/fp"


def vault_get(path):
    req = urllib.request.Request(f"{VAULT_URL}/v1/{path}")
    req.add_header("X-Vault-Token", VAULT_TOKEN)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def etcd_put(key, value):
    body = json.dumps({
        "key":   base64.b64encode(key.encode()).decode(),
        "value": base64.b64encode(value.encode()).decode(),
    }).encode()
    req = urllib.request.Request(f"{ETCD_URL}/v3/kv/put", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def main():
    print("-> Lese XOSP Fingerprint aus Vault...")
    try:
        resp = vault_get("secret/data/xosp/identity")
        fp = resp["data"]["data"]["fingerprint"]
    except Exception as e:
        print(f"❌ Fingerprint nicht in Vault: {e}")
        print("   Laeuft XOSP? (make app)")
        sys.exit(1)

    print(f"   Fingerprint: {fp[:16]}...")
    print(f"-> Schreibe in etcd: {ETCD_KEY}")

    try:
        etcd_put(ETCD_KEY, fp)
    except Exception as e:
        print(f"❌ etcd schreiben fehlgeschlagen: {e}")
        sys.exit(1)

    print("✅ Fingerprint registriert — XOS neu starten")


if __name__ == "__main__":
    main()
