# Absolute local_dir in config.json

**Date:** 2026-05-21  
**Task:** Support and document absolute paths for `local_dir` in config.json.

## What was done

- Confirmed `local_root_path()` uses absolute paths as-is (no project-root prefix).
- Clarified error message for JSON on Windows (forward slashes or escaped backslashes).
- Updated `config.example.json` to show an absolute Windows-style path.

## Files changed

- `upload.py` — clearer absolute-path handling and error hint
- `config.example.json` — absolute path example

## User prompt

I want put absoulute path for local_dir
