# Local upload path in config.json

**Date:** 2026-05-21  
**Task:** Let upload.py read the local folder to upload from `config.json` instead of only `upload_config.json`.

## What was done

- `merge_config_json_settings()` now reads `local_dir` from `config.json` (overrides `upload_config.json` when set).
- Added `local_root_path()` to resolve relative paths from the project root or use an absolute path.
- `local_dir` is required in either `config.json` or `upload_config.json`.
- Startup prints the resolved local upload folder path.
- Added `config.example.json` with `local_dir` and other common keys.

## Files changed

- `upload.py` — config.json `local_dir` support and path resolution
- `config.example.json` — example status/config file with `local_dir`

## User prompt

upload behavior, I want put folder path inside config.json so upload.py can upload all files inside the specified path.
