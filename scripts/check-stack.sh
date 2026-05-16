#!/usr/bin/env bash
# scripts/check-stack.sh — quick health probe for the local stack.
# Verifies that Postgres, Keycloak and Ollama (with the required models) respond.
# Exits non-zero on the first failure so it can be chained in CI or pre-demo checks.

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { printf "${GREEN}✓${NC} %s\n" "$1"; }
fail() { printf "${RED}✗${NC} %s\n" "$1"; exit 1; }
note() { printf "${YELLOW}…${NC} %s\n" "$1"; }

# Load env if available so the script can be invoked from anywhere.
if [[ -f "$(dirname "$0")/../.env" ]]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' "$(dirname "$0")/../.env" | xargs)
fi

PG_USER="${POSTGRES_USER:-rag}"
PG_DB="${POSTGRES_DB:-rag}"
LLM_MODEL="${OLLAMA_LLM_MODEL:-llama3.1:8b}"
EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"

note "Checking Postgres (db)…"
docker compose exec -T db pg_isready -U "$PG_USER" -d "$PG_DB" >/dev/null \
  && ok "Postgres responds (pg_isready)" \
  || fail "Postgres is not ready"

note "Checking pgvector extension…"
docker compose exec -T db psql -U "$PG_USER" -d "$PG_DB" -tAc \
  "SELECT 1 FROM pg_extension WHERE extname='vector';" | grep -q 1 \
  && ok "pgvector extension installed" \
  || fail "pgvector extension is NOT installed in '$PG_DB'"

note "Checking Keycloak readiness…"
curl --silent --fail "http://localhost:8080/realms/rag/.well-known/openid-configuration" >/dev/null \
  && ok "Keycloak realm 'rag' is reachable" \
  || fail "Keycloak realm 'rag' did not respond"

note "Checking Ollama API…"
curl --silent --fail "http://localhost:11434/api/tags" >/dev/null \
  && ok "Ollama API responds" \
  || fail "Ollama API is not responding"

note "Checking Ollama models are pulled…"
MODELS_JSON="$(curl --silent http://localhost:11434/api/tags)"
echo "$MODELS_JSON" | grep -q "\"$LLM_MODEL\"" \
  && ok "LLM model '$LLM_MODEL' is available" \
  || fail "LLM model '$LLM_MODEL' is NOT pulled. Run: docker compose run --rm ollama-init"

echo "$MODELS_JSON" | grep -q "\"$EMBED_MODEL\"" \
  && ok "Embedding model '$EMBED_MODEL' is available" \
  || fail "Embedding model '$EMBED_MODEL' is NOT pulled. Run: docker compose run --rm ollama-init"

printf "\n${GREEN}Stack is healthy.${NC}\n"
