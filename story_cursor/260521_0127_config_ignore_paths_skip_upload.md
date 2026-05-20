# Ignore paths in config.json

**Date:** 2026-05-21  
**Task:** Skip certain files and folders during upload using an ignore list in config.json.

## What was done

- Added `ignore` array in `config.json` (and `config.sqlite` meta after sync).
- Pattern types: folder/file segment (`build`, `.git`), path prefix (`platforms/android-33`), globs (`*.tmp`).
- Scan skips ignored directories entirely (no descent) for performance.
- Ignored paths are not hashed, cached, or uploaded.
- `config.json` overrides sqlite meta when both define `ignore`.

## Files changed

- `upload.py` — `path_matches_ignore`, scan filtering, startup print of patterns
- `status_store.py` — migrate `ignore` meta key
- `config.example.json` — example ignore list

## User prompt

I want put ignore settings for certail files or folder so upload.py doesn't handle those files and skip it. I want put ignore files or folders as list inside config.json
