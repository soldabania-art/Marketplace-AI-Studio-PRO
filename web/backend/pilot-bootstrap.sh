#!/bin/sh
set -eu
ENV_FILE=${1:-.env.pilot}
[ -f "$ENV_FILE" ] || { echo "missing $ENV_FILE; copy .env.pilot.example" >&2; exit 1; }
if grep -n 'CHANGE_ME' "$ENV_FILE" >/dev/null; then
  echo "refusing to start: replace all CHANGE_ME placeholders in $ENV_FILE" >&2
  exit 1
fi
case "$(grep '^MARKETPLACE_ENVIRONMENT=' "$ENV_FILE" | cut -d= -f2-)" in
  production|prod) echo "refusing production environment in local pilot compose" >&2; exit 1;;
esac
exec docker compose --env-file "$ENV_FILE" -f docker-compose.pilot.yml up -d --build
