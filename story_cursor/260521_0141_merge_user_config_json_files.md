# Merge user config files into single config.json

**Date:** 2026-05-21  
**Task:** Merge upload_config.json and config.json into one config.json for the user.

## What was done

- Wrote merged `config.json` with SSH/server settings from `upload_config.json` and `local_dir` / `ignore` from the previous `config.json`.
- Set `status_file` to `config.sqlite` (per-file progress, not JSON).
- Removed legacy `files` and `uploaded_success` keys from the merged file.
- Renamed `upload_config.json` → `upload_config.json.bak` (backup).
- Verified `load_settings()` loads the merged file correctly.

## Files changed

- `config.json` — merged settings (gitignored, not committed)
- `upload_config.json.bak` — backup of old upload config (gitignored)

## User prompt

do the things for me
