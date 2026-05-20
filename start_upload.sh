#!/usr/bin/env bash
# Start SFTP upload (uses upload.sh -> upload.py with project .venv if present).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting upload..."
echo "  Exit codes: 0=ok, 1=auth, 2=SSH lost, 3=network down, 4=stall timeout"
echo "  Progress is saved in config.json on exit — restart to resume."
echo

UPLOAD_SH="$SCRIPT_DIR/upload.sh"
if [[ ! -f "$UPLOAD_SH" ]]; then
  echo "upload.sh not found in $SCRIPT_DIR" >&2
  exit 1
fi

chmod +x "$UPLOAD_SH" 2>/dev/null || true
set +e
"$UPLOAD_SH"
exit_code=$?
set -e

if [[ "$exit_code" -ne 0 ]]; then
  echo
  case "$exit_code" in
    2) echo "SSH session lost. Progress saved — run again to resume." ;;
    3) echo "Network unavailable. Progress saved — fix connection and run again." ;;
    4) echo "No data transferred within stall_timeout_seconds. Progress saved — run again." ;;
    *) echo "Upload exited with code $exit_code." ;;
  esac
fi

exit "$exit_code"
