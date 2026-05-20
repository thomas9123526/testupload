# Usage JSON rotation at 2MB

**Date:** 2026-05-20
**Task:** Rotate usage.json to numbered archives when it exceeds 2MB.

## What was done

- Before each usage write, if `usage.json` is 2MB or larger it is renamed to the next archive file (`usage_0000.json`, then `usage_0001.json`, etc.).
- A fresh empty `usage.json` is then used for new entries.
- Optional override: `CALCULATE_HASH_USAGE_MAX_BYTES` for the size limit.

## Files changed

- `linux/calculate_hash.py` — rotation helpers and pre-write check

## User prompt

if the usage.json is bigger than 2m, create another one like usage_0004.json, so first usage.json will be renamed usage_0000.json
