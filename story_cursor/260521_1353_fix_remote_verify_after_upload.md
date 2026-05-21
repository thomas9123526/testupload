# Fix remote verify after upload

**Date:** 2026-05-21
**Task:** Fix post-upload verification failure and misleading authentication error in auto_upload.

## What was done

- Diagnosed that SFTP upload can succeed while SSH exec verification fails (idle exec session or hash timeout).
- Added `VerificationFailedError` with expected vs actual size/hash in the message (exit code 6).
- Reconnect SSH exec and retry verify up to 3 times after each upload.
- Keep stall timer alive while waiting for `calculate_hash.py` on the server.
- Only treat JSON `not_found` as missing file (not every exit code 1).
- Updated `auto_upload.py` to map exit 6 to verification failure instead of authentication error.

## Files changed

- `upload.py` — verify retries, exec reconnect, clearer errors, exit 6
- `auto_upload.py` — exit code 5/6 error messages

## User prompt

I start upload.bat and successfully uploaded for "C:\Users\aaa\source\testupload\material\0520\AndResGuard-master.zip", but after upload finish for this file i get error like this.
Traceback (most recent call last):
  File "C:\Users\aaa\source\testupload\upload.py", line 1108, in <module>
    sys.exit(main())
  File "C:\Users\aaa\source\testupload\upload.py", line 1076, in main
    return process_files(settings)
  File "C:\Users\aaa\source\testupload\upload.py", line 1050, in process_files
    raise RuntimeError("Upload finished but remote verification failed.")
RuntimeError: Upload finished but remote verification failed.

Upload failed: authentication error (exit 1). Check upload_config.json credentials.
Retry interval: 300s (config.json: auto_upload_retry_seconds)
Retrying upload in 276 seconds... (press any key to retry now)

I run this on powershell which launched from start menu
