# Fix SSH authentication error handling

**Date:** 2026-05-20  
**Task:** Handle AuthenticationException without traceback; improve credential config.

## What was done

- Catch `AuthenticationException` in `main()` and print a clear message (exit code 1).
- Strip whitespace from password; allow optional `private_key_path` instead of password.
- Added `ssh_connect_kwargs()` for password or key-based login.

## Files changed

- `upload.py` — auth error handling and key support
- `upload_config.example.json` — document `private_key_path`

## User prompt

PS C:\Users\aaa\source\testupload> .\start_upload.bat
...
paramiko.ssh_exception.AuthenticationException: Authentication failed: transport shut down or saw EOF

Upload script exited with code 1.
