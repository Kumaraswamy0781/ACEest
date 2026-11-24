#!/usr/bin/env bash
set +x
set -euo pipefail

kube() {
    minikube -p aceest kubectl -- --context=aceest -n aceest "$@"
}

existing=$(kube get secret aceest-runtime --ignore-not-found -o name)
if [ -n "$existing" ]; then
    echo "Reusing existing aceest-runtime Secret."
    exit 0
fi

claim=$(kube get pvc data-aceest-postgres-0 --ignore-not-found -o name)
if [ -n "$claim" ]; then
    echo "PostgreSQL storage exists but aceest-runtime is missing. Restore the original credentials first." >&2
    exit 1
fi

umask 077
env_file=$(mktemp "${TMPDIR:-/tmp}/aceest-runtime.XXXXXX")
trap 'rm -f "$env_file"' EXIT
password=$(openssl rand -hex 24)
session_key=$(openssl rand -hex 32)
{
    printf 'POSTGRES_PASSWORD=%s\n' "$password"
    printf 'ACEEST_SECRET_KEY=%s\n' "$session_key"
    printf 'ACEEST_DATABASE_URL=postgresql+psycopg://aceest:%s@aceest-postgres:5432/aceest\n' "$password"
} > "$env_file"

kube create secret generic aceest-runtime --from-env-file="$env_file"
