# Server-side calculate_hash.py via SSH exec

**Date:** 2026-05-20  
**Task:** Add linux/calculate_hash.py and server-side hash via SSH (not SFTP).

## What was done

- Added **`linux/calculate_hash.py`** — server script: `python3 calculate_hash.py /path/to/file` → JSON `{size, sha256}`.
- **SFTP cannot run scripts** — upload.py uses a **separate SSH connection** for `exec_command` while SFTP handles uploads.
- On connect: checks `server_calculate_hash_script` exists on server via SFTP `stat`.
- Config: **`server_calculate_hash_script`** in `upload_config.json` or **`config.json`** (config.json overrides).
- Falls back to SFTP download+hash if script missing or exec fails.

## Deploy

1. Upload `linux/calculate_hash.py` to server, e.g. `/home/st78326/calculate_hash.py`
2. `chmod +x calculate_hash.py`
3. In local **config.json** or **upload_config.json**:
   ```json
   "server_calculate_hash_script": "/home/st78326/calculate_hash.py"
   ```

## User prompt

I want put shell script to server disk. Let's call it calculate_hash.py ... can upload.py let calculate_hash.py do the calculation via sftp?
