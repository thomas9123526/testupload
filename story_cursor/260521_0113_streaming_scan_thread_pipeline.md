# Streaming scan thread pipeline

**Date:** 2026-05-21  
**Task:** Add scan thread and bounded queues so millions of files do not load into memory or block startup.

## What was done

- **Thread 1 (scan):** `os.scandir` walk streams paths into bounded `scan_queue` (8192); builds `known_paths` incrementally.
- **Thread 2 (hash):** Consumes scan queue; same hash/cache/upload logic as before.
- **Thread 3 (cache):** Unchanged; final prune only when `known_paths` non-empty.
- **Thread 4 (upload):** Lazy remote mkdir per file; only ensures remote base at start (removed full-tree `sync_remote_directory_tree` before upload).
- **`iter_local_files`:** No `rglob` + `sorted` + giant list.
- **Dashboard:** Four rows — Scan | Hash | Cache | Upload with running counts.
- **Backpressure:** Full scan queue blocks scan until hash catches up.
- **Empty folder:** Scan joins first; skips SSH if zero files.

## Files changed

- `upload.py` — scan worker, streaming iterator, pipeline orchestration

## User prompt

let's do it
