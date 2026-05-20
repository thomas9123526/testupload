# Add start_upload launchers

**Date:** 2026-05-20  
**Task:** Create `start_upload.sh` (Linux) and `start_upload.bat` (Windows) to start uploading.

## What was done

- Added `start_upload.sh` — changes to project directory, ensures `upload.sh` is executable, runs `upload.sh` (which uses `.venv` Python and `upload.py`).
- Added `start_upload.bat` — prints a short status line, calls `upload.bat` if present, otherwise falls back to `upload.py` with venv/system Python.

## Files changed

- `start_upload.sh` — Linux/macOS entry point
- `start_upload.bat` — Windows entry point

## User prompt

I want  you make start_upload.sh for linux and start_upload.bat for windows that start uploading via upload.sh or upload.py
