# Track successful uploads in config.json filename list

**Date:** 2026-05-20  
**Task:** Save successfully uploaded filenames in config.json.

## What was done

- Added `uploaded_success` array to `config.json` — sorted list of relative paths under `material/` that finished successfully.
- List is rebuilt automatically on each save from `files` entries with `status: "uploaded"`.
- Existing `files` detail (size, sha256, action) kept for resume/skip logic.
- Done summary prints count of successful files in config.

## Example config.json

```json
{
  "version": 1,
  "uploaded_success": [".gitkeep", "docs/readme.txt"],
  "files": { ... }
}
```

## Files changed

- `upload.py` — `sync_uploaded_success_list()`, save/load integration

## User prompt

I want modify scripts for upload task.
I want put filenames that upload successed in @config.json
