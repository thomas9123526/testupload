# Calculate hash usage logging

**Date:** 2026-05-20
**Task:** Log each server-side hash script run to usage.json with user, time, and per-file execution count.

## What was done

- Updated `linux/calculate_hash.py` to record every successful hash request in `usage.json` next to the script on the server.
- Each entry uses the resolved absolute file path as the JSON key, with `execution_count` and an `executions` list of `{user, time}` records.
- User is taken from `LOGNAME` / `USER` / `USERNAME` or `getpass.getuser()`; timestamp format is `YYYY-MM-DD HH:MM:SS` (local server time).
- Optional override via `CALCULATE_HASH_USAGE_FILE` environment variable; writes use a temp file and atomic replace.

## Files changed

- `linux/calculate_hash.py` — usage tracking and usage.json persistence

## User prompt

I want modify calculate_hash.py

So calculate_hash.py calculate hash for files on server side.
I want save the script usage like script execution with user , time(like 2026-05-20 12:13:00) to usage.json file.
the usage.json should contain the key as absolute file path(@linux/calculate_hash.py  accepts as argument ) and reference count or execution count ,
