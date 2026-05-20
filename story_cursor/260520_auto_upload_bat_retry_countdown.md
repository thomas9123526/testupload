# Add auto_upload.bat with retry countdown

**Date:** 2026-05-20  
**Task:** Create auto_upload.bat — run upload.py, success in green, error in red with countdown retry.

## What was done

- Added `auto_upload.bat` — loops upload.py until exit 0; Ctrl+C stops (130).
- Exit 0 → green **Auto Upload Is Finished**.
- Error → red message by exit code, countdown retry (reads interval each loop).
- Added `read_auto_upload_retry.py` — reads `auto_upload_retry_seconds` from config.json (default 300).
- Set `auto_upload_retry_seconds: 300` in config.json; preserve key in upload.py load_status.
- Documented in upload_config.example.json.

## Config (config.json)

```json
"auto_upload_retry_seconds": 300
```

## Usage

```powershell
.\auto_upload.bat
```

## Files changed

- `auto_upload.bat`, `read_auto_upload_retry.py`
- `upload.py` — preserve auto_upload_retry_seconds default in config.json
- `upload_config.example.json`, `config.json`

## User prompt

I want make a auto_upload.bat to do the following:

Step 1. start upload.py and then wait until upload.py finished with exit code.
Step 2. if the execution finished then analyze the  exit code and then do the task based on the exit code.

1) if exit code = 0 then finith auto_upload.bat with printing "Auto Upload Is Finished " with green color.
2) if there's error ,  then print the message why upload.py fails with red color and wait 300 seconds. show count down seconds in the console while waiting 300 seconds.
after 300 seconds restart upload from step1 again. here 300 seconds can be set in config.json and so auto_upload.bat can read it again from the config.json. put default value for 300 seconds to config.json
