# Add auto_upload.py and upload.bat

**Date:** 2026-05-20  
**Task:** Python auto-upload loop with retry countdown; upload.bat to run it.

## What was done

- Added **`auto_upload.py`** — runs `upload.py`, handles exit codes:
  - **0** → green `Auto Upload Is Finished`
  - **Error** → red message, countdown from `config.json` `auto_upload_retry_seconds` (default 300), retry
  - **130** → stop on Ctrl+C
- Re-reads retry interval from **config.json** before each wait.
- Added **`upload.bat`** — runs `auto_upload.py` with project `.venv` Python.

## Config (config.json)

```json
"auto_upload_retry_seconds": 300
```

## Usage

```powershell
.\upload.bat
```

or

```powershell
python auto_upload.py
```

## Files changed

- `auto_upload.py` — auto upload loop
- `upload.bat` — launcher

## User prompt

First. I want make a auto_upload.py to do the following:
[loop upload.py, exit 0 green success, error red + countdown from config.json auto_upload_retry_seconds default 300]

Second. give me upload.bat to execute auto_upload.py
