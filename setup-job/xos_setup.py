#!/usr/bin/env python3
"""
xos_setup.py -- Konfiguriert den kompletten XOS Stack.

Ablauf:
  1. Warte auf Vault, MinIO, Keycloak, etcd
  2. Konfiguriere Vault (PKI, Policy, KV Secrets, JWT Auth)
  3. Konfiguriere MinIO Bucket
  4. Konfiguriere Keycloak (Realm, Clients, Benutzer, Mapper)
  5. Schreibe komplette Config in etcd (IAM + Infra + XOSP)
  6. Konfiguriere Vault K8s Auth (nur in K8s)

JWT enthaelt nur noch: groups, email, preferred_username
Alles andere kommt aus etcd.
XOS verbindet sich direkt zu XOSP auf localhost:9100 (kein Reverse Proxy).
Keycloak laeuft auf Port 8080 direkt (kein HAProxy).
"""

import sys, os, json, time, secrets, string, ssl, base64, socket
import urllib.request, urllib.error, hashlib, hmac
from datetime import datetime, timezone

def _env(key, default):
    return os.environ.get(key, default)

NAMESPACE      = _env("XOS_NAMESPACE",      "xos-dev")
NIP_BASE       = _env("XOS_NIP_BASE",       "127.0.0.1.nip.io")
MINIO_USER     = _env("XOS_MINIO_USER",     "xos-minio")
KEYCLOAK_ADMIN = _env("XOS_KEYCLOAK_ADMIN", "admin")
VAULT_TOKEN    = "xos-dev-root-token"

PG_PASS        = _env("XOS_PG_PASS",        "xos-pg-bootstrap")
MINIO_PASS     = _env("XOS_MINIO_PASS",     "xos-minio-bootstrap")
KEYCLOAK_PASS  = _env("XOS_KEYCLOAK_PASS",  "xos-kc-bootstrap")
MEMGRAPH_PASS  = _env("XOS_MEMGRAPH_PASS",  "xos-memgraph-bootstrap")

def _gen(length=32):
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(length))

XOSP_SECRET    = _env("XOS_XOSP_SECRET",    "xos-xosp-demo-secret-2026")
USER_PASS      = _env("XOS_USER_PASS",      "xos-dev-2026")
LIVEKIT_SECRET = _env("XOS_LIVEKIT_SECRET", _gen())

VAULT_URL     = _env("XOS_VAULT_URL",     "http://vault:8200")
MINIO_URL     = _env("XOS_MINIO_URL",     "http://minio:9000")
KEYCLOAK_URL  = _env("XOS_KEYCLOAK_URL",  "http://keycloak:8080")
ETCD_HOST     = _env("XOS_ETCD_HOST",     "etcd")
ETCD_PORT     = int(_env("XOS_ETCD_PORT", "2379"))
MEMGRAPH_HOST = _env("XOS_MEMGRAPH_HOST", "memgraph")
PG_HOST       = _env("XOS_PG_HOST",       "postgresql")
LIVEKIT_URL   = "ws://livekit:7880"

# XOSP URL -- per Env-Var konfigurierbar, Default: localhost:9100
XOSP_URL       = _env("XOS_XOSP_URL",       "https://localhost:9100")

# Externe URLs -- Ports direkt ohne HAProxy
EXT_KEYCLOAK   = f"http://keycloak.{NIP_BASE}:8080"
EXT_VAULT      = f"http://openbao.{NIP_BASE}:8200"
EXT_IAM_ISSUER = f"http://keycloak.{NIP_BASE}:8080/realms/xos"

K8S_CA_CERT  = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
K8S_SA_TOKEN = "/var/run/secrets/kubernetes.io/serviceaccount/token"
K8S_API      = "https://kubernetes.default.svc"

OK   = "✓  "
WARN = "⚠️  "
INFO = "->  "

# -- HTTP Helpers --------------------------------------------------------------

def http_call(method, url, body=None, headers=None):
    headers = headers or {}
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    for k, v in headers.items():
        req.add_header(k, v)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            content = r.read()
            return r.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        content = e.read().decode()
        try:
            return e.code, json.loads(content)
        except Exception:
            return e.code, {"raw": content}

def vault_post(path, body=None):
    status, resp = http_call("POST", f"{VAULT_URL}/v1/{path}", body,
                             {"X-Vault-Token": VAULT_TOKEN})
    if status >= 400:
        errors = resp.get("errors", [str(resp)])
        if any("already in use" in str(e) or "already exists" in str(e) for e in errors):
            return resp
        raise Exception(f"vault POST {path}: HTTP {status}: {errors}")
    return resp

def vault_put(path, body=None):
    status, resp = http_call("PUT", f"{VAULT_URL}/v1/{path}", body,
                             {"X-Vault-Token": VAULT_TOKEN})
    if status >= 400:
        raise Exception(f"vault PUT {path}: HTTP {status}: {resp}")
    return resp

def kc(method, path, body=None, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return http_call(method, f"{KEYCLOAK_URL}/admin/realms{path}", body, headers)

def kc_set_mappers(client_id, mapper_defs, token):
    _, clients = kc("GET", f"/xos/clients?clientId={client_id}", token=token)
    if not clients:
        return
    cid = clients[0]["id"]
    _, mappers = kc("GET", f"/xos/clients/{cid}/protocol-mappers/models", token=token)
    existing = {m.get("name") for m in (mappers if isinstance(mappers, list) else [])}
    for name, body in mapper_defs:
        if name not in existing:
            kc("POST", f"/xos/clients/{cid}/protocol-mappers/models", body=body, token=token)
        else:
            mapper = next((m for m in mappers if m.get("name") == name), None)
            if mapper:
                kc("PUT", f"/xos/clients/{cid}/protocol-mappers/models/{mapper['id']}",
                   body={**mapper, **body}, token=token)

def etcd_put(key, value):
    url = f"http://{ETCD_HOST}:{ETCD_PORT}/v3/kv/put"
    body = {
        "key":   base64.b64encode(key.encode()).decode(),
        "value": base64.b64encode(value.encode()).decode(),
    }
    status, resp = http_call("POST", url, body)
    if status != 200:
        raise Exception(f"etcd put {key}: HTTP {status}: {resp}")

# -- Credentials speichern -----------------------------------------------------

def k8s_secret_write(name, data):
    if not os.path.exists(K8S_SA_TOKEN):
        os.makedirs("/run/xos", exist_ok=True)
        with open(f"/run/xos/{name}.env", "w") as f:
            for k, v in data.items():
                f.write(f"{k}={v}\n")
        return
    with open(K8S_SA_TOKEN) as f:
        token = f.read().strip()
    encoded = {k: base64.b64encode(v.encode()).decode() for k, v in data.items()}
    body = json.dumps({
        "apiVersion": "v1", "kind": "Secret",
        "metadata": {"name": name, "namespace": NAMESPACE},
        "data": encoded,
    }).encode()
    ctx = ssl.create_default_context(cafile=K8S_CA_CERT)
    url = f"{K8S_API}/api/v1/namespaces/{NAMESPACE}/secrets"
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10):
            return
    except urllib.error.HTTPError as e:
        if e.code != 409:
            raise
    req = urllib.request.Request(f"{url}/{name}", data=body, method="PUT")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, context=ctx, timeout=10):
        return

# -- Wait Helpers --------------------------------------------------------------

def wait_for(name, check_fn, timeout=600):
    print(f"{INFO}Warte auf {name}...", end="", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if check_fn():
                print(" bereit")
                return
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(5)
    print()
    raise Exception(f"{name} nicht erreichbar nach {timeout}s")

def vault_ready():
    status, _ = http_call("GET", f"{VAULT_URL}/v1/sys/health")
    return status == 200

def minio_ready():
    status, _ = http_call("GET", f"{MINIO_URL}/minio/health/live")
    return status == 200

def keycloak_ready():
    status, _ = http_call("GET", f"{KEYCLOAK_URL}/realms/master")
    return status == 200

def etcd_ready():
    try:
        s = socket.create_connection((ETCD_HOST, ETCD_PORT), timeout=3)
        s.close()
        return True
    except Exception:
        return False

# -- Vault ---------------------------------------------------------------------

def setup_vault():
    print("\n-- OpenBao ------------------------------------------------")
    vault_post("sys/mounts/secret", {"type": "kv", "options": {"version": "2"}})
    print(f"{OK}KV v2")
    vault_post("sys/mounts/pki", {"type": "pki", "config": {"max_lease_ttl": "8760h"}})
    vault_post("pki/root/generate/internal", {"common_name": "XOS Root CA", "ttl": "8760h"})
    for role, client_flag, server_flag, domains in [
        ("xos-server",    False, True,  ["localhost", "127.0.0.1", NIP_BASE,
                                         f"xosp.{NIP_BASE}", f"{NAMESPACE}.svc.cluster.local"]),
        ("xos-db-client", True,  False, ["xosp", "xoso", "admin", "operator"]),
        ("xos-role",      True,  True,  ["localhost", "127.0.0.1", NIP_BASE,
                                         f"xosp.{NIP_BASE}", f"{NAMESPACE}.svc.cluster.local"]),
    ]:
        vault_post(f"pki/roles/{role}", {
            "allowed_domains": domains, "allow_subdomains": True,
            "allow_bare_domains": True, "allow_ip_sans": True,
            "client_flag": client_flag, "server_flag": server_flag, "max_ttl": "720h",
        })
    print(f"{OK}PKI")
    vault_post("sys/policies/acl/xos-policy", {"policy": """
path "secret/data/xos"            { capabilities = ["create","read","update","delete","list"] }
path "secret/data/xos/*"          { capabilities = ["create","read","update","delete","list"] }
path "secret/data/xosp/*"         { capabilities = ["create","read","update","delete","list"] }
path "pki/issue/xos-role"         { capabilities = ["create","update"] }
path "pki/issue/xos-server"       { capabilities = ["create","update"] }
path "pki/issue/xos-db-client"    { capabilities = ["create","update"] }
path "pki/ca/pem"                 { capabilities = ["read"] }
"""})
    print(f"{OK}Policy")
    _, xos_cert = http_call("POST", f"{VAULT_URL}/v1/pki/issue/xos-server",
        {"common_name": "localhost", "alt_names": "localhost",
         "ip_sans": "127.0.0.1", "ttl": "8760h"},
        {"X-Vault-Token": VAULT_TOKEN})
    ca_req = urllib.request.Request(f"{VAULT_URL}/v1/pki/ca/pem")
    ca_req.add_header("X-Vault-Token", VAULT_TOKEN)
    with urllib.request.urlopen(ca_req, timeout=10) as r:
        ca_pem = r.read().decode()
    k8s_secret_write("xos-tls", {
        "xos_cert": xos_cert.get("data", {}).get("certificate", ""),
        "xos_key":  xos_cert.get("data", {}).get("private_key", ""),
        "ca_cert":  ca_pem,
    })
    print(f"{OK}TLS Certs ausgestellt")
    vault_put("secret/data/xos", {"data": {
        "PG_PASS":        PG_PASS,
        "MINIO_USER":     MINIO_USER,
        "MINIO_PASS":     MINIO_PASS,
        "MEMGRAPH_PASS":  MEMGRAPH_PASS,
        "XOSP_SECRET":    XOSP_SECRET,
        "LIVEKIT_SECRET": LIVEKIT_SECRET,
        "LIVEKIT_URL":    LIVEKIT_URL,
    }})
    print(f"{OK}KV Secrets")

def setup_vault_k8s_auth():
    print("\n-- OpenBao K8s Auth ---------------------------------------")
    with open(K8S_CA_CERT) as f:
        k8s_ca = f.read()
    with open(K8S_SA_TOKEN) as f:
        sa_token = f.read().strip()
    vault_post("sys/auth/kubernetes", {"type": "kubernetes"})
    vault_post("auth/kubernetes/config", {
        "kubernetes_host": K8S_API,
        "kubernetes_ca_cert": k8s_ca,
        "token_reviewer_jwt": sa_token,
    })
    vault_post("auth/kubernetes/role/xos", {
        "bound_service_account_names": ["xos"],
        "bound_service_account_namespaces": [NAMESPACE],
        "policies": ["xos-policy"], "ttl": "1h",
    })
    print(f"{OK}K8s Auth + Rolle 'xos'")

# -- MinIO ---------------------------------------------------------------------

def setup_minio():
    print("\n-- MinIO --------------------------------------------------")
    now = datetime.now(timezone.utc)
    date_str     = now.strftime("%Y%m%d")
    datetime_str = now.strftime("%Y%m%dT%H%M%SZ")
    region, service, bucket = "us-east-1", "s3", "xos-html"
    payload_hash = hashlib.sha256(b"").hexdigest()
    host = MINIO_URL.replace("http://", "")
    canonical_headers = f"host:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{datetime_str}\n"
    signed_headers     = "host;x-amz-content-sha256;x-amz-date"
    canonical_request  = "\n".join(["PUT", f"/{bucket}/", "", canonical_headers, signed_headers, payload_hash])
    credential_scope   = f"{date_str}/{region}/{service}/aws4_request"
    string_to_sign     = "\n".join(["AWS4-HMAC-SHA256", datetime_str, credential_scope,
                                    hashlib.sha256(canonical_request.encode()).hexdigest()])
    def sign(key, msg):
        return hmac.new(key, msg.encode(), hashlib.sha256).digest()
    signing_key = sign(sign(sign(sign(f"AWS4{MINIO_PASS}".encode(), date_str), region), service), "aws4_request")
    signature   = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    auth = (f"AWS4-HMAC-SHA256 Credential={MINIO_USER}/{credential_scope},"
            f"SignedHeaders={signed_headers},Signature={signature}")
    req = urllib.request.Request(f"{MINIO_URL}/{bucket}/", data=b"", method="PUT")
    req.add_header("Host", host)
    req.add_header("X-Amz-Date", datetime_str)
    req.add_header("X-Amz-Content-Sha256", payload_hash)
    req.add_header("Authorization", auth)
    req.add_header("Content-Length", "0")
    try:
        with urllib.request.urlopen(req, timeout=10):
            print(f"{OK}Bucket: {bucket}")
    except urllib.error.HTTPError as e:
        if e.code == 409:
            print(f"{OK}Bucket existiert: {bucket}")
        else:
            raise Exception(f"Bucket {bucket}: HTTP {e.code}")

# -- Keycloak ------------------------------------------------------------------

def keycloak_admin_token():
    body = f"grant_type=password&client_id=admin-cli&username={KEYCLOAK_ADMIN}&password={KEYCLOAK_PASS}"
    req  = urllib.request.Request(
        f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token",
        data=body.encode(), method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["access_token"]

def setup_keycloak():
    print("\n-- Keycloak -----------------------------------------------")
    token = keycloak_admin_token()
    status, _ = kc("GET", "/xos", token=token)
    if status == 404:
        kc("POST", "", body={"realm": "xos", "enabled": True, "displayName": "XOS",
                              "sslRequired": "none", "registrationAllowed": False}, token=token)
    print(f"{OK}Realm: xos")
    for group in ["xos-admin", "xos-manager", "xos-user", "xos-lager"]:
        _, resp = kc("GET", f"/xos/groups?search={group}", token=token)
        if not any(g["name"] == group for g in (resp if isinstance(resp, list) else [])):
            kc("POST", "/xos/groups", body={"name": group}, token=token)
    print(f"{OK}Gruppen")
    for username, firstname, lastname, email, group in [
        ("frank",   "Frank",   "Meier", "frank@xium.ai",   "xos-admin"),
        ("tristan", "Tristan", "Meier", "tristan@xium.ai", "xos-user"),
    ]:
        _, users = kc("GET", f"/xos/users?username={username}", token=token)
        if not users:
            kc("POST", "/xos/users", body={
                "username": username, "firstName": firstname,
                "lastName": lastname, "email": email, "enabled": True,
                "credentials": [{"type": "password", "value": USER_PASS, "temporary": False}],
            }, token=token)
            _, users = kc("GET", f"/xos/users?username={username}", token=token)
        _, groups = kc("GET", f"/xos/groups?search={group}", token=token)
        if users and groups:
            kc("PUT", f"/xos/users/{users[0]['id']}/groups/{groups[0]['id']}", token=token)
    print(f"{OK}Benutzer: frank + tristan  (Passwort: {USER_PASS})")
    _, clients = kc("GET", "/xos/clients?clientId=xos", token=token)
    xos_client_body = {
        "clientId": "xos", "enabled": True, "publicClient": True,
        "redirectUris": ["*"], "webOrigins": ["*"],
        "standardFlowEnabled": True,
        "attributes": {"pkce.code.challenge.method": "S256"},
    }
    if not clients:
        kc("POST", "/xos/clients", body=xos_client_body, token=token)
    else:
        kc("PUT", f"/xos/clients/{clients[0]['id']}",
           body={**clients[0], **xos_client_body}, token=token)
    kc_set_mappers("xos", [
        ("groups", {
            "name": "groups", "protocol": "openid-connect",
            "protocolMapper": "oidc-group-membership-mapper",
            "config": {"full.path": "false", "id.token.claim": "true",
                       "access.token.claim": "true", "userinfo.token.claim": "true",
                       "claim.name": "groups"},
        }),
    ], token)
    print(f"{OK}XOS Client (JWT: nur groups)")
    _, clients = kc("GET", "/xos/clients?clientId=xosp", token=token)
    if not clients:
        kc("POST", "/xos/clients", body={
            "clientId": "xosp", "enabled": True, "publicClient": False,
            "secret": XOSP_SECRET,
            "serviceAccountsEnabled": True, "standardFlowEnabled": False,
        }, token=token)
    else:
        kc("PUT", f"/xos/clients/{clients[0]['id']}",
           body={**clients[0], "secret": XOSP_SECRET}, token=token)
    kc_set_mappers("xosp", [
        ("xosp-audience", {
            "name": "xosp-audience", "protocol": "openid-connect",
            "protocolMapper": "oidc-audience-mapper",
            "config": {"included.client.audience": "xosp",
                       "id.token.claim": "false", "access.token.claim": "true"},
        }),
    ], token)
    print(f"{OK}XOSP Client")

# -- Vault JWT Auth ------------------------------------------------------------

def setup_vault_jwt():
    print("\n-- OpenBao JWT --------------------------------------------")
    jwks_url = f"{KEYCLOAK_URL}/realms/xos/protocol/openid-connect/certs"
    vault_post("sys/auth/jwt", {"type": "jwt"})
    vault_post("auth/jwt/config", {"jwks_url": jwks_url, "default_role": "xos-role", "bound_issuer": ""})
    vault_post("auth/jwt/role/xos-role", {
        "role_type": "jwt", "bound_audiences": ["xos"],
        "user_claim": "email", "groups_claim": "groups",
        "policies": ["xos-policy"], "ttl": "1h",
    })
    vault_post("auth/jwt/role/xosp-role", {
        "role_type": "jwt", "bound_audiences": ["xosp"],
        "user_claim": "sub", "policies": ["xos-policy"], "ttl": "1h",
    })
    print(f"{OK}xos-role + xosp-role")

# -- etcd -- komplette XOS + XOSP Konfiguration --------------------------------
# XOSP URL kommt aus Env-Var XOS_XOSP_URL (Default: https://localhost:9100)
# XOSP Fingerprint wird aus Vault gelesen (XOSP schreibt ihn beim Start).
# Damit kann man URL und Fingerprint ohne Rebuild aendern.

def read_xosp_fingerprint_from_vault(timeout=120):
    """Wartet bis XOSP seinen Fingerprint in Vault geschrieben hat."""
    print(f"{INFO}Warte auf XOSP Fingerprint in Vault...", end="", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            status, resp = http_call(
                "GET",
                f"{VAULT_URL}/v1/secret/data/xosp/identity",
                headers={"X-Vault-Token": VAULT_TOKEN},
            )
            if status == 200:
                fp = resp.get("data", {}).get("data", {}).get("fingerprint", "")
                if fp:
                    print(f" {fp[:16]}...")
                    return fp
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(5)
    print()
    raise Exception(f"XOSP Fingerprint nicht in Vault nach {timeout}s — laeuft XOSP?")


def setup_etcd():
    print("\n-- etcd ---------------------------------------------------")
    entries = {
        "/xos/config/iam_issuer_url":  EXT_IAM_ISSUER,
        "/xos/config/iam_client_id":   "xos",
        "/xos/config/iam_scope":       "openid profile email",
        "/xos/config/vault_url":       EXT_VAULT,
        "/xos/config/html_type":       "s3",
        "/xos/config/html_dir":        "xos-html",
        "/xos/services/xosp/url":      XOSP_URL,
        "/xos/services/xosp/backend":  "memgraph",
        "/xos/services/xosp/dsn":      f"bolt://memgraph:{MEMGRAPH_PASS}@{MEMGRAPH_HOST}:7687",
        "/xos/services/xosp/dsn_demo": f"postgres://postgres:{PG_PASS}@{PG_HOST}:5432/xium?sslmode=disable",
    }
    for key, value in entries.items():
        etcd_put(key, value)
        print(f"{OK}{key} = {value}")



# -- Zusammenfassung -----------------------------------------------------------

def print_summary():
    memgraph_dsn = f"bolt://memgraph:{MEMGRAPH_PASS}@localhost:7687"
    print("\n" + "=" * 60)
    print("XOS CREDENTIALS")
    print("=" * 60)
    print(f"OpenBao Token  : {VAULT_TOKEN}  (Dev-Modus)")
    print(f"OpenBao UI     : {EXT_VAULT}/ui")
    print()
    print(f"Keycloak Admin : {KEYCLOAK_ADMIN} / {KEYCLOAK_PASS}")
    print(f"Keycloak URL   : {EXT_KEYCLOAK}/admin")
    print()
    print(f"MinIO User     : {MINIO_USER} / {MINIO_PASS}")
    print(f"MinIO Console  : http://minio-console.{NIP_BASE}:9001")
    print()
    print(f"Memgraph       : {memgraph_dsn}")
    print(f"Benutzer       : frank + tristan  /  {USER_PASS}")
    print()
    print(f"XOSP           : {XOSP_URL}")
    print(f"XOS starten:   xos --etcd localhost:2379")
    print(f"xoso --uri \"{memgraph_dsn}\"")
    print("=" * 60)

# -- Main ----------------------------------------------------------------------

def main():
    print("=" * 60)
    print("XOS Stack Setup")
    print("=" * 60)

    wait_for("OpenBao",  vault_ready)
    wait_for("MinIO",    minio_ready)
    wait_for("Keycloak", keycloak_ready)
    wait_for("etcd",     etcd_ready)

    print(f"\n{INFO}Speichere Credentials...")
    k8s_secret_write("xos-credentials", {
        "pg_pass":        PG_PASS,
        "pg_dsn":         f"postgres://postgres:{PG_PASS}@{PG_HOST}:5432/xium?sslmode=disable",
        "minio_user":     MINIO_USER,
        "minio_pass":     MINIO_PASS,
        "keycloak_pass":  KEYCLOAK_PASS,
        "memgraph_user":  "memgraph",
        "memgraph_pass":  MEMGRAPH_PASS,
        "memgraph_dsn":   f"bolt://memgraph:{MEMGRAPH_PASS}@{MEMGRAPH_HOST}:7687",
        "xosp_secret":    XOSP_SECRET,
        "livekit_secret": LIVEKIT_SECRET,
        "user_pass":      USER_PASS,
        "vault_token":    VAULT_TOKEN,
    })
    print(f"{OK}Credentials gespeichert")

    errors = []
    for name, fn in [
        ("OpenBao",     setup_vault),
        ("MinIO",       setup_minio),
        ("Keycloak",    setup_keycloak),
        ("OpenBao JWT", setup_vault_jwt),
        ("etcd",        setup_etcd),
    ]:
        try:
            fn()
        except Exception as e:
            print(f"{WARN}{name}: {e}")
            errors.append(name)

    if os.path.exists(K8S_SA_TOKEN):
        try:
            setup_vault_k8s_auth()
        except Exception as e:
            print(f"{WARN}OpenBao K8s Auth: {e}")

    print_summary()
    print("\n" + "=" * 60)
    if errors:
        print(f"Fehlgeschlagen: {', '.join(errors)}")
        sys.exit(1)
    else:
        print("✅ XOS Stack vollstaendig konfiguriert")
    print("=" * 60)

if __name__ == "__main__":
    main()
