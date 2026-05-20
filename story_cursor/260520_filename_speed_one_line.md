# Filename and transfer speed on one progress line

**Date:** 2026-05-20  
**Task:** Show filename together with transfer speed during upload.

## What was done

- Added `format_progress_line()` combining label, bytes, percent, and speed.
- Progress updates on one line: `[1/11] path/file — 1.2 MB / 5.0 MB ( 24.0%) @ 512.3 KB/s`
- Removed separate "... uploading" line before progress.

## Files changed

- `upload.py` — combined progress display

## User prompt

yes
