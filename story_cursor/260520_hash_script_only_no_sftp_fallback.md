# Require calculate_hash.py only, remove SFTP hash fallback

**Date:** 2026-05-20  
**Task:** Remove SFTP download+hash fallback; server hash via calculate_hash.py only.

## What was done

- Removed `remote_file_info_via_sftp` and all SFTP hash fallback paths.
- `server_calculate_hash_script` is **required** in upload_config.json or config.json.
- Deploy or exec failure raises `ServerHashScriptError` (exit 5) — no fallback.
- Remote verify/compare uses `calculate_hash.py` on server only.

## User prompt

I want remove logic for step4 on Flow on connect above.
4. If deploy fails → fall back to SFTP hash (download + hash locally).   I want remove this logic and upload.py have to calculate the server file hash via only calculate_hash.py
