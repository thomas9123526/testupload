# Single config.json for all settings

**Date:** 2026-05-21  
**Task:** Combine upload_config.json and config.json into one config.json.

## What was done

- `load_settings()` reads only `config.json` (see `config.example.json` for full template).
- Legacy `upload_config.json` fills **missing** keys only (in-memory), with a note to consolidate.
- Removed `merge_config_json_settings()` overlay; no more config vs upload_config priority fight.
- Per-file progress stays in `config.sqlite` (`status_file`).
- Updated `status_store`, `auto_upload.py`, `start_upload.bat`, deprecated `upload_config.example.json`.

## Files changed

- `upload.py`, `status_store.py`, `config.example.json`, `upload_config.example.json`, `auto_upload.py`, `start_upload.bat`, `.cursor/rules/task-commit-and-story.mdc`

## User prompt

single one
