#!/usr/bin/env bash
# Validate Garden Irrigation Home Assistant integration release readiness.
set -euo pipefail

expected_version=""
if [[ "${1:-}" == "--expect-version" ]]; then
  expected_version="${2:-}"
  if [[ -z "$expected_version" ]]; then
    echo "Missing value for --expect-version" >&2
    exit 2
  fi
  shift 2
fi

if (($#)); then
  echo "Unknown arguments: $*" >&2
  exit 2
fi

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

python3 -m json.tool hacs.json >/dev/null
python3 -m json.tool custom_components/garden_irrigation/manifest.json >/dev/null
python3 -m json.tool custom_components/garden_irrigation/strings.json >/dev/null
find tests/fixtures -name '*.json' -print0 | xargs -0 -r -n1 python3 -m json.tool >/dev/null

manifest_version="$(
  python3 - <<'PY'
import json
from pathlib import Path

manifest = json.loads(
    Path("custom_components/garden_irrigation/manifest.json").read_text(
        encoding="utf-8"
    )
)
print(manifest["version"])
PY
)"

if [[ -n "$expected_version" && "$manifest_version" != "$expected_version" ]]; then
  echo "manifest.json version $manifest_version does not match $expected_version" >&2
  exit 2
fi

case "$manifest_version" in
  [0-9]*.[0-9]*.[0-9]*) ;;
  *)
    echo "manifest.json version must be semver-like x.y.z: $manifest_version" >&2
    exit 2
    ;;
esac

python3 -m compileall -q custom_components/garden_irrigation tests
python3 -m unittest discover -s tests

legacy_hits="$(
  rg -n 'garden-irrigation-wifi|garden_irrigation_wifi' \
    custom_components tests README.md docs dashboards home-assistant/dashboards \
    2>/dev/null || true
)"
if [[ -n "$legacy_hits" ]]; then
  echo "Found legacy garden-irrigation-wifi references:" >&2
  echo "$legacy_hits" >&2
  exit 2
fi

test -f custom_components/garden_irrigation/manifest.json
test -f custom_components/garden_irrigation/config_flow.py
test -f custom_components/garden_irrigation/protocol.py
test -f custom_components/garden_irrigation/services.yaml

echo "Garden Irrigation HA integration release check OK ($manifest_version)."
