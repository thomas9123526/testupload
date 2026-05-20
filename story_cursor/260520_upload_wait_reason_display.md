# Show wait/pause reason with stall countdown

**Date:** 2026-05-20  
**Task:** Print why upload is pending, waiting, or paused when there is no progress.

## What was done

- Extended `TransferTracker` with `set_activity(activity, detail)` for current task.
- After 2s idle, console shows: `Waiting: {reason} (idle Ns, stall in Ns)`.
- Activity set for: network check, SSH connect, SFTP open, remote folders, remote hash read, upload, verify.
- Stall error message includes what the script was doing when stalled.

## Example

```
      Waiting: Reading remote file hash — [3/11] docs/big.pdf (idle 45s, stall in 555s)
```

## Files changed

- `upload.py` — activity tracking and wait status display

## User prompt

also modify upload.py to print information why it's pending or waiting or paused to console when there's no progress for upload.py
