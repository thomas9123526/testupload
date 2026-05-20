# Usage JSON hash per execution

**Date:** 2026-05-20
**Task:** Store sha256 and size in usage.json for each hash script execution.

## What was done

- Each execution entry in `usage.json` now includes `sha256` and `size` alongside `user` and `time`.
- Hash is computed once per run and reused for both stdout JSON and usage logging.

## Files changed

- `linux/calculate_hash.py` — pass hash/size into `record_usage`

## User prompt

i want put hash values also in the usage.json for a file per execution
