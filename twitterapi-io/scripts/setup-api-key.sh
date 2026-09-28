#!/usr/bin/env bash
set -euo pipefail

config_dir="${HOME}/.config/twitterapi-io"
config_file="${config_dir}/config.json"

# Existing vault-backed credentials rotate in the vault, never back into plaintext.
if reference="$(python3 - "$config_file" <<'PYREF'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
value = json.loads(path.read_text()).get("api_key") if path.exists() else None
if isinstance(value, dict) and set(value) == {"$agent_secret"} and isinstance(value["$agent_secret"], str) and value["$agent_secret"]:
    print(value["$agent_secret"])
else:
    raise SystemExit(1)
PYREF
 )"; then
  exec "$HOME/.local/bin/secrets" set "$reference"
fi

mkdir -p "$config_dir"
chmod 700 "$config_dir"

printf "twitterapi.io API key: "
IFS= read -rs api_key
printf "\n"
if [ -z "$api_key" ]; then
  printf "No API key entered. Nothing changed.\n" >&2
  exit 1
fi

printf '%s' "$api_key" | python3 -c '
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
api_key = sys.stdin.read()
data = json.loads(path.read_text()) if path.exists() else {}
data["api_key"] = api_key
path.write_text(json.dumps(data, indent=2) + "\n")
path.chmod(0o600)
' "$config_file"

printf "Saved twitterapi.io API key to %s\n" "$config_file"
printf "Next run: %s/twitterapi-io help\n" "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
