# Fix SSH Channel closed and auto-reconnect

**Date:** 2026-05-20  
**Task:** Fix upload failing with "SSH session lost: Channel closed" right after connect.

## What was done

- Added connect retries (3 attempts) with clearer steps (`Opening SFTP session...`).
- Stopped using `exec_command` for remote file checks; use SFTP `stat` + streamed SHA-256 instead (shared hosts often drop extra SSH channels).
- Auto-reconnect and resume the upload queue when the session drops mid-run.
- Treat `"channel closed"` as a disconnect; strip trailing slash from `server_upload_path`.

## Files changed

- `upload.py` — connection, SFTP-only verify, reconnect logic

## User prompt

PS C:\Users\aaa\source\testupload> .\start_upload.bat
Starting upload...

Scanning local files...
Found 11 file(s). 11 need upload/check, 0 already marked uploaded.

Connecting to st78326@64.20.33.250:22 ...

✗ SSH session lost: Channel closed.
Script stopped. Start it again manually to resume from config.json.

Upload script exited with code 2.
