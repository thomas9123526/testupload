# Auto upload countdown key skip

**Date:** 2026-05-20
**Task:** Allow pressing any key during retry countdown to start upload immediately.

## What was done

- Replaced fixed `time.sleep(1)` countdown with per-second key detection on Windows (`msvcrt`) and Unix TTY (`select` + `termios`).
- During "Retrying upload in N seconds...", any keypress ends the wait and starts the next upload run right away.
- Countdown message now hints that a keypress skips the wait.

## Files changed

- `auto_upload.py` — `wait_one_second_or_key()` and updated `countdown()`

## User prompt

I want modify auto_upload.py

So when the script enter "Retrying upload in ..." part, the script count down seconds.

But if the user press any key then break the count down and go next upload immediately
