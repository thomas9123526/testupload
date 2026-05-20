# Exit on network failure and transfer stall timeout

**Date:** 2026-05-20  
**Task:** Exit upload on bad network or zero-byte stall; configurable timeout; update start scripts.

## What was done

- Exit immediately when server is unreachable (`NetworkUnavailableError`, exit 3) — no infinite wait.
- Exit when no bytes transfer for `stall_timeout_seconds` (default 600) in **upload_config.json** (`TransferStalledError`, exit 4).
- Removed auto-reconnect loops; progress stays in `config.json` after each successful file.
- `TransferTracker` + watchdog during uploads and remote hash reads.
- Updated `start_upload.bat` / `start_upload.sh` with exit code messages.

## Config (upload_config.json)

```json
"stall_timeout_seconds": 600
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Auth failed |
| 2 | SSH session lost |
| 3 | Network unavailable |
| 4 | Stall timeout (no data) |

## Files changed

- `upload.py` — network check, stall tracker, exit behavior
- `upload_config.example.json` — `stall_timeout_seconds`
- `start_upload.bat`, `start_upload.sh` — exit messages

## User prompt

modify start_upload.bat or start_upload.sh to do the following.

If network connection is bad or can't connect linux server then exit the whole process with saving progress status to config.json that is used when restart.

Also exit the whole process if the script transfer no data ( zero byte, means there's no data transfer) in a 10 minutes.
This time limit can be set via config.json
