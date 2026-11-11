#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ -n "${PYTHON_BIN:-}" ]; then
  PY="$PYTHON_BIN"
else
  PY=""
  for candidate in python3 python3.13 python3.12 python3.11 python3.10; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
      PY="$candidate"
      break
    fi
  done
fi
if [ -z "$PY" ] || ! "$PY" -c 'import sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
  echo "rea-video requires Python >= 3.10; set PYTHON_BIN to a compatible interpreter" >&2
  exit 1
fi
exec "$PY" "$ROOT/scripts/manage_install.py" --source "$ROOT" "$@"
