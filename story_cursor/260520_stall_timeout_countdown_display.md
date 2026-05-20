# Show stall timeout countdown in console

**Date:** 2026-05-20  
**Task:** Display countdown of stall_timeout_seconds while waiting for data transfer.

## What was done

- `TransferTracker` watchdog prints live countdown each second: `stall timeout in 582s`
- Resets to full limit when bytes transfer; clears line on exit or stall abort.
- Watchdog polls every 1s (was 5s) for smoother countdown.

## Files changed

- `upload.py` — TransferTracker countdown display

## User prompt

I want modify upload.py to show count down stall_timeout_seconds to console
