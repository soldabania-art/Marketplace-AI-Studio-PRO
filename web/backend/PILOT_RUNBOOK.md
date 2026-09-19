# Isolated non-production backend pilot

This local/non-production API + worker smoke stack is not a production readiness claim. It creates no paid hosting resources and does not expose PostgreSQL or Redis ports.

## Start

```sh
cp .env.pilot.example .env.pilot
# Generate local secrets without printing them into shell history:
python -c 'import secrets; print(secrets.token_hex(32))' # use as POSTGRES_PASSWORD
# Generate Fernet keys locally; place two different values in .env.pilot.
sh pilot-bootstrap.sh
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/ready
```

The bootstrap refuses placeholders, non-development environments, short JWTs, invalid or reused Fernet keys, and non-hex PostgreSQL passwords. It runs the existing one-shot `alembic upgrade head` service before API/worker.

This compose file is local-only: it binds the API to localhost and uses development guards. Do not expose it directly to the internet or use it as a hosted production deployment. A hosted pilot needs the existing production guards (PostgreSQL TLS, HTTPS frontend/API behind a reverse proxy, real secret injection, MFA/STOP policy) and is outside this compose file.

Before applying migrations to an existing pilot, stop API and worker first:

```sh
docker compose --env-file .env.pilot -f docker-compose.pilot.yml stop api worker
docker compose --env-file .env.pilot -f docker-compose.pilot.yml run --rm migrate
docker compose --env-file .env.pilot -f docker-compose.pilot.yml up -d api worker
```

## Observe and stop

```sh
docker compose --env-file .env.pilot -f docker-compose.pilot.yml ps
docker compose --env-file .env.pilot -f docker-compose.pilot.yml logs -f api worker migrate
docker compose --env-file .env.pilot -f docker-compose.pilot.yml down
```

Add `-v` to `down` only when intentionally deleting the pilot database volume.
