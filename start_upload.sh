#!/usr/bin/env bash
# Start SFTP upload (uses upload.sh -> upload.py with project .venv if present).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

UPLOAD_SH="$SCRIPT_DIR/upload.sh"
if [[ ! -f "$UPLOAD_SH" ]]; then
  echo "upload.sh not found in $SCRIPT_DIR" >&2
  exit 1
fi

chmod +x "$UPLOAD_SH" 2>/dev/null || true
exec "$UPLOAD_SH"
