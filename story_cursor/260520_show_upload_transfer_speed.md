# Show upload transfer speed in console

**Date:** 2026-05-20  
**Task:** Display file transfer speed while uploading.

## What was done

- Added `format_speed()` helper for human-readable rates (B/s, KB/s, MB/s).
- Upload progress line now shows live speed: `progress: 1.2 MB / 5.0 MB ( 24.0%) @ 512.3 KB/s`.
- On completion, prints final line with average speed.

## Files changed

- `upload.py` — speed in `upload_with_retry` progress callback

## User prompt

I want show transfer file speed in the console when uploading
