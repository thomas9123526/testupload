#!/usr/bin/env bash
# Run start_upload.sh in a loop; on error wait loop_upload_interval seconds and retry.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -x ".venv/bin/python" ]]; then
  PYTHON=".venv/bin/python"
else
  PYTHON="python3"
fi

INTERVAL="$("$PYTHON" "$SCRIPT_DIR/read_loop_interval.py")"
START_UPLOAD="$SCRIPT_DIR/start_upload.sh"

if [[ ! -f "$START_UPLOAD" ]]; then
  echo "start_upload.sh not found in $SCRIPT_DIR" >&2
  exit 1
fi

chmod +x "$START_UPLOAD" 2>/dev/null || true

echo "Loop upload — monitoring start_upload.sh"
echo "  Retry interval: ${INTERVAL}s (loop_upload_interval in upload_config.json or config.json)"
echo "  Exit 0 = done; non-zero error = wait and retry; Ctrl+C = stop"
echo

while true; do
  set +e
  "$START_UPLOAD"
  exit_code=$?
  set -e

  if [[ "$exit_code" -eq 0 ]]; then
    echo
    echo "Upload finished successfully. Loop stopped."
    exit 0
  fi

  if [[ "$exit_code" -eq 130 ]]; then
    echo
    echo "Interrupted. Loop stopped."
    exit 130
  fi

  echo
  echo "Upload exited with error code $exit_code."
  echo "Progress saved in config.json. Retrying in ${INTERVAL}s ..."
  sleep "$INTERVAL"
  echo
done
