# Isolated non-production backend pilot

This local/non-production API + worker smoke stack is not a production readiness claim. It creates no paid hosting resources and does not expose PostgreSQL or Redis ports.

## Start

```sh
cp .env.pilot.example .env.pilot
# Replace CHANGE_ME values; generate Fernet values with:
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
./pilot-bootstrap.sh .env.pilot
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/ready
```

The `migrate` service runs `alembic upgrade head` once and API/worker wait for its successful completion. The worker runs `python -m app.worker`; API runs with the embedded FBO monitor disabled.

This compose file is local-only: it binds the API to localhost and uses development guards. Do not expose it directly to the internet or use it as a hosted production deployment. A hosted pilot needs the existing production guards (PostgreSQL TLS, HTTPS frontend/API behind a reverse proxy, real secret injection, MFA/STOP policy) and is outside this compose file.

Before applying migrations to an existing pilot, stop API and worker first, then run the migration explicitly:

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
