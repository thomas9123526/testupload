# Read retry interval from config.json only

**Date:** 2026-05-20  
**Task:** auto_upload.bat reads INTERVAL from config.json auto_upload_retry_seconds.

## What was done

- Removed hardcoded `set "INTERVAL=300"` in `:read_interval`.
- `read_auto_upload_retry.py` reads only `config.json` → `auto_upload_retry_seconds` (default 300 if missing).
- Re-reads each retry loop before countdown.

## Files changed

- `auto_upload.bat` — dynamic INTERVAL from config.json
- `read_auto_upload_retry.py` — config.json only

## User prompt

I want modify auto_upload.bat to read INTERVAL from auto_upload_retry_seconds fields in @config.json 
you can find the code like 'set "INTERVAL=300"' in line55
