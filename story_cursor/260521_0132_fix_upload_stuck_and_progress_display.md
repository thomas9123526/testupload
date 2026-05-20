# Fix upload appearing stuck; show file transfer progress

**Date:** 2026-05-21  
**Task:** Upload looked frozen after 10+ minutes; user could not see per-file upload progress.

## Root cause

- Upload thread did **not** start until the **entire local tree scan finished** (`scan_thread.join()` before SSH). Android SDK scan can take a very long time, so Upload stayed at 0 with no activity.
- Python threads have **equal** priority; upload was blocked on the pipeline order, not CPU priority.
- During transfer, the dashboard was **hidden** (`upload_busy` skipped status refresh) and progress used `\r` on a conflicting line.

## What was done

- Start **SSH + upload thread while scan/hash continue** (removed early `scan_thread.join()`).
- Upload queue wait shows phase: `waiting (scanning)`, `waiting (hashing)`, `comparing`, `uploading`, `verifying`.
- Dashboard always refreshes; adds **Phase** row and **File** row with bytes/speed during upload.
- Per-file progress updates `upload_file_line` in the live dashboard instead of hiding it.

## Files changed

- `upload.py` — orchestration order, progress UI, `upload_with_retry` progress hook

## User prompt

i also start upload.bat about 10 minutes ago, But I notice that upload progress is stuck.
So the thread for uploading files has lower priority?
Also I can't see the current file progress uploading status with necessary.
