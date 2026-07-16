#!/usr/bin/env bash
# Builds the env-var arguments for `vercel deploy` by overlaying the Doppler
# config (selected by the config-scoped service token in $DOPPLER_TOKEN) onto
# an optional committed env-file base. Doppler wins per key; the file fills the
# rest. Used by both deploy.yml jobs so dev/staging/prod all ship env vars the
# same way (no Doppler->Vercel sync, no dashboard env vars).
#
# Usage: doppler_env_args.sh [--base-file <path>] [--build-env]
#   --base-file  committed config-only env file (KEY=value, # comments) used as
#                the base layer (frontend .env.dev/.env.staging)
#   --build-env  additionally emit each key as --build-env (frontend builds
#                inline NEXT_PUBLIC_* at build time); default emits --env only
#
# Emits NUL-delimited args so multiline values (PEM keys) survive:
#   readarray -d '' env_args < <(bash doppler_env_args.sh ...)
set -euo pipefail

base_file=""
emit_build_env=false
while [ $# -gt 0 ]; do
  case "$1" in
    --base-file) base_file="$2"; shift 2 ;;
    --build-env) emit_build_env=true; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

declare -A envmap=()
declare -a order=()

set_kv() {
  local key="$1" value="$2"
  if [[ -z "${envmap[$key]+x}" ]]; then order+=("$key"); fi
  envmap[$key]="$value"
}

# Base layer: committed env file. Values are single-line and space-free by the
# env-file contract (they travel as CLI flag arguments).
if [[ -n "$base_file" ]]; then
  while IFS= read -r raw; do
    line="${raw%%#*}"
    line="$(printf '%s' "$line" | tr -d '[:space:]')"
    [[ -z "$line" ]] && continue
    set_kv "${line%%=*}" "${line#*=}"
  done < "$base_file"
fi

# Overlay: the full Doppler config. Values are base64-wrapped so multiline
# secrets (PEM keys) survive the line-based read; blank Doppler values override
# the file base deliberately, mirroring `doppler run` precedence.
# Captured via command substitution (NOT process substitution) so a failing
# doppler download aborts the script under pipefail — otherwise a deploy could
# silently ship without secrets (e.g. no EDGE_AUTH_SECRET = edge check open).
python_bin="$(command -v python3 || command -v python)"
doppler_b64="$(doppler secrets download --no-file --format json | "$python_bin" -c '
import base64, json, sys
for key, value in json.load(sys.stdin).items():
    print(key + "=" + base64.b64encode(str(value).encode()).decode())
')"
while IFS= read -r entry; do
  entry="${entry%$'\r'}" # tolerate CRLF from a Windows python (local runs)
  [[ -z "$entry" ]] && continue
  key="${entry%%=*}"
  case "$key" in DOPPLER_PROJECT|DOPPLER_CONFIG|DOPPLER_ENVIRONMENT) continue ;; esac
  set_kv "$key" "$(printf '%s' "${entry#*=}" | base64 -d)"
done <<< "$doppler_b64"

for key in "${order[@]}"; do
  printf -- '--env\0%s=%s\0' "$key" "${envmap[$key]}"
  if $emit_build_env; then
    printf -- '--build-env\0%s=%s\0' "$key" "${envmap[$key]}"
  fi
done
