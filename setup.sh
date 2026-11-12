#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

if [[ ! -f .env ]]; then
  umask 077
  cp .env.example .env
  echo '.env mit lokalen Ollama-Voreinstellungen erstellt.'
fi
if ! grep -q '^POSTGRES_PASSWORD=' .env; then
  password="$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')"
  printf '\nPOSTGRES_PASSWORD=%s\n' "$password" >> .env
  echo 'Zufaelliges Datenbankpasswort in .env ergaenzt.'
fi

command -v docker >/dev/null 2>&1 || {
  echo 'Docker fehlt. Installiere Docker Desktop mit WSL2 und Linux-Containern.' >&2
  exit 1
}
docker compose version >/dev/null
docker info >/dev/null
docker compose config --quiet
mkdir -p output

# Erst die externen Abhaengigkeiten pruefen, bevor der Stack gebaut wird.
docker compose run --rm --no-deps hermes-init /opt/hermes/.venv/bin/python /project/scripts/check_services.py
docker compose build honcho
docker compose up -d --wait database redis honcho
docker compose up -d honcho-deriver
# Keine parallelen Schreibvorgaenge waehrend einer erneuten Konfiguration.
docker compose stop hermes
docker compose run --rm hermes-init
docker compose up -d hermes
echo 'Setup fertig. Chat: docker compose exec -u hermes hermes hermes chat'
echo 'Job testen: docker compose exec -u hermes hermes hermes cron run shopping-daily'
