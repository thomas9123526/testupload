# Auto-deploy calculate_hash.py to server

**Date:** 2026-05-20  
**Task:** Upload linux/calculate_hash.py to server automatically when missing.

## What was done

- Added `deploy_server_hash_script()` — SFTP upload of `linux/calculate_hash.py` to `server_calculate_hash_script` path.
- On connect: if server script missing, deploy local copy then enable server-side hashing.
- Falls back to SFTP hash if deploy fails.

## User prompt

sure
