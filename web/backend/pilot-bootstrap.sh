#!/bin/sh
set -eu
ENV_FILE=.env.pilot
[ -f "$ENV_FILE" ] || { echo "missing $ENV_FILE; copy .env.pilot.example" >&2; exit 1; }
python - "$ENV_FILE" <<'PY'
import base64, binascii, re, sys
vals={}
for line in open(sys.argv[1], encoding="utf-8"):
    if line.strip() and not line.startswith("#") and "=" in line:
        k,v=line.rstrip("\n").split("=",1); vals[k]=v
if any("CHANGE_ME" in v for v in vals.values()):
    raise SystemExit("refusing to start: replace all CHANGE_ME placeholders in .env.pilot")
if vals.get("MARKETPLACE_ENVIRONMENT") != "development":
    raise SystemExit("refusing to start: pilot requires MARKETPLACE_ENVIRONMENT=development")
if len(vals.get("MARKETPLACE_JWT_SECRET","")) < 32:
    raise SystemExit("refusing to start: JWT secret must be at least 32 characters")
pw=vals.get("POSTGRES_PASSWORD","")
if not re.fullmatch(r"[0-9a-fA-F]{32,}", pw):
    raise SystemExit("refusing to start: POSTGRES_PASSWORD must be hex, at least 32 characters")
keys=[]
for name in ("MARKETPLACE_MARKETPLACE_TOKEN_KEY","MARKETPLACE_MFA_ENCRYPTION_KEY"):
    try:
        raw=base64.urlsafe_b64decode(vals.get(name,"")+"===")
    except (binascii.Error, ValueError):
        raise SystemExit("refusing to start: invalid Fernet key")
    if len(raw)!=32: raise SystemExit("refusing to start: Fernet keys must decode to 32 bytes")
    keys.append(raw)
if keys[0] == keys[1]: raise SystemExit("refusing to start: Fernet keys must be different")
PY
exec docker compose --env-file "$ENV_FILE" -f docker-compose.pilot.yml up -d --build
