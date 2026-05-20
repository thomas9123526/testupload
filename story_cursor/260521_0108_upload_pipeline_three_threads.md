# Upload pipeline with three threads

**Date:** 2026-05-21  
**Task:** Run hash, cache save, and upload work in parallel with mutexes, queues, and a live status dashboard.

## What was done

- **Thread 1 (hash):** Scans files, resolves or computes SHA-256, enqueues `UploadJob` when `needs_upload`, pushes new hashes to `pending_cache`.
- **Thread 2 (cache):** Watches `cache_dirty`, merges pending hashes into `cache.json` incrementally (faster restarts).
- **Thread 3 (upload):** Consumes ready queue after SSH connect; compare, upload, verify; saves `config.json` per file.
- **Synchronization:** `cache_lock`, `status_lock`, `print_lock`, `Queue`, `threading.Event`.
- **Status UI:** Live 3-row dashboard (hash / cache / upload bars and current file).
- Upload can start while hashing continues (queue blocks until each file is ready).

## Dependency order

1. Hash before upload (upload needs size + sha256).
2. Cache writer runs after each new hash (does not block hash or upload).
3. SSH connect + folder sync in main thread before upload thread starts.
4. Hash + cache threads start immediately after file scan.

## Files changed

- `upload.py` — pipeline classes, workers, refactored `process_files`

## User prompt

I want implement some thread and mutes for the following task inside the upload.py
1. A thread that runs on the local files to calculate hash and put each result to some variables.
2. A thread that monitor variables and if new values then read and save to the cache.json for reduce time when we restart process.
3. A thread that start uploading for files that is finished hash calculating and ready to go.

I want above 3 threads run simulatenously but you should think about the dependencies and the order what to do inside each thread.

I want output the status of the above 3 progress in a nice pattern.
