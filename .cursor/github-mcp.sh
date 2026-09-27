#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "$ROOT/.env" ]]; then
  set -a
  source "$ROOT/.env"
  set +a
fi

if [[ -z "${GITHUB_PAT:-}" ]]; then
  echo "GITHUB_PAT is not set. Add it to .env" >&2
  exit 1
fi

export GITHUB_PERSONAL_ACCESS_TOKEN="$GITHUB_PAT"
export GITHUB_TOOLSETS="pull_requests"
export GITHUB_READ_ONLY="true"
export PATH="/Users/kaushan/.nvm/versions/node/v20.20.2/bin:/usr/bin:/bin"

exec /Users/kaushan/.nvm/versions/node/v20.20.2/bin/node \
  /Users/kaushan/.nvm/versions/node/v20.20.2/lib/node_modules/npm/bin/npx-cli.js \
  -y @modelcontextprotocol/server-github
