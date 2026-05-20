# Loop upload scripts with configurable retry interval

**Date:** 2026-05-20  
**Task:** Add loop_upload.sh / loop_upload.bat to retry start_upload on error after a delay.

## What was done

- Added `loop_upload.bat` (Windows) and `loop_upload.sh` (Linux) — run `start_upload`, monitor exit code.
- Exit **0** → stop loop (success).
- Exit **non-zero** (except 130) → wait `loop_upload_interval` seconds, retry.
- Exit **130** (Ctrl+C) → stop loop.
- Added `read_loop_interval.py` to read interval from `upload_config.json` or `config.json` (default 300s / 5 min).
- Documented `loop_upload_interval` in `upload_config.example.json`.

## Config

In `upload_config.json` or `config.json`:

```json
"loop_upload_interval": 300
```

## Usage

```powershell
.\loop_upload.bat
```

```bash
chmod +x loop_upload.sh
./loop_upload.sh
```

## Files changed

- `loop_upload.bat`, `loop_upload.sh` — retry loop
- `read_loop_interval.py` — reads `loop_upload_interval`
- `upload_config.example.json` — example setting

## User prompt

I want you make a loop_upload.sh and loop_upload.bat do the following.

1. exec start_upload.sh or start_upload.bat and monitor while  for the execution.
2. if the execution finished then analyze the execution result based on exit code and if there's error ,  restart the start_upload.sh or start_upload.bat again. but after 5 minutes later. This 5 minutes can be configured through config.json file as loop_upload_interval
