# SQLite status store for millions of files

**Date:** 2026-05-21  
**Task:** Replace monolithic config.json load/save with scalable per-file storage so startup and progress saves stay fast.

## What was done

- Added `status_store.py` — SQLite `config.sqlite` with `meta` and `files` tables (WAL mode).
- Per-file `upsert_file()` on each upload/skip (no full-file rewrite).
- Per-file `get_file()` for hash skip and `needs_upload` checks (no loading millions of rows at once).
- Auto-migration from legacy `config.json` on first run (batched inserts).
- Default `status_file` → `config.sqlite` in `upload_config.example.json`.
- Updated `upload.py`, `read_auto_upload_retry.py`, `auto_upload.py`.
- Removed `uploaded_success` list rebuild (use `COUNT(*)` query instead).

## Files changed

- `status_store.py` — new
- `upload.py` — StatusStore integration
- `read_auto_upload_retry.py`, `auto_upload.py` — read meta from SQLite
- `upload_config.example.json`, `config.example.json`, `.gitignore`

## User prompt

I see, @config.json  is problem when millions of files. Will be large. I want solution for this , so there's no delay to load and save
