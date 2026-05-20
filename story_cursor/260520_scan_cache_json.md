# Local scan cache for append-only material folder

**Date:** 2026-05-20  
**Task:** Speed up scanning by caching SHA-256 in cache.json for unchanged files.

## What was done

- Added **`cache.json`** — stores `size` + `sha256` per file under `material/`.
- On scan, reuse hash from **config.json** (uploaded files) or **cache.json** when size matches — no full disk read.
- Only **new files** are hashed; existing files skip SHA-256 (fits append-only workflow).
- Prune cache entries for removed paths; save after each scan.
- Setting **`scan_cache_file`** in upload_config.json (default `cache.json`).

## Example output

```
Scanning local files...
Found 500 file(s). 497 from cache, 3 hashed. 3 need upload/check, 497 already marked uploaded.
```

## Files changed

- `upload.py` — scan cache load/save and cached local_file_info
- `.gitignore` — ignore cache.json
- `upload_config.example.json` — scan_cache_file

## User prompt

=== Starting upload.py ===
Scanning local files...

this take many times. Is there any solution to reduce this by using cache or cache.json ...
