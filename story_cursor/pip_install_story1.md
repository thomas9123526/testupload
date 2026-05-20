# Cursor conversation story: testupload setup

**Project:** `c:\Users\aaa\source\testupload`  
**Date:** May 20, 2026  
**Topic:** Git ignore, SFTP upload config, dependencies, and running `upload.py`

---

## 1. Add `.gitignore`

**User:** Put git ignore.

**What we did:**
- Confirmed/created `.gitignore` for a Python SFTP upload project.
- Ignored: `.venv/`, `__pycache__/`, `*.pyc`, `upload_config.json`, `config.json`, `config.json.tmp`.
- Ignored all content under `material/` while keeping the folder in git via `material/.gitkeep`.

**`.gitignore` (material section):**

```gitignore
material/**
!material/.gitkeep
```

`material/**` ignores nested files and subfolders, not only top-level entries.

---

## 2. Ignore everything inside `material/`

**User:** I want ignore all content inside material.

**Change:** Replaced `material/*` with `material/**` for recursive ignore. Kept `!material/.gitkeep` so the empty folder can still be committed.

If files were already tracked:

```bash
git rm -r --cached material/
```

---

## 3. Install dependencies in the project

**User:** To execute `upload.py`, please download dependencies to project.

**What we did:**
- Dependencies live in project virtualenv: `.venv/`
- Installed from `requirements.txt`:

```powershell
cd c:\Users\aaa\source\testupload
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**`requirements.txt`:**

```
pycaw>=20240210
paramiko>=3.4.0
```

For `upload.py`, the required package is **paramiko** (SFTP). `pycaw` is for `enable_audio.py`.

**Run upload:**

```powershell
.\upload.bat
# or
.\.venv\Scripts\python.exe upload.py
```

`.venv/` is gitignored; each machine needs its own venv.

---

## 4. Server upload path in config

**User:** Put server folder path in `upload_config.json` so uploads go to that path on the server.

**What we did:**
- Added **`server_upload_path`** in `upload_config.json` / `upload_config.example.json`.
- Uploader reads this and mirrors local `material/` under that path on the server.
- Legacy key `remote_dir` still works as a fallback but `server_upload_path` is preferred.

**Example `upload_config.example.json`:**

```json
{
  "host": "YOUR_HOST",
  "port": 22,
  "username": "YOUR_USER",
  "password": "YOUR_PASSWORD_HERE",
  "local_dir": "material",
  "server_upload_path": "/home/YOUR_USER/public_html/material",
  "status_file": "config.json",
  "network_check_interval_seconds": 10,
  "ssh_connect_timeout_seconds": 30
}
```

Copy `upload_config.example.json` → `upload_config.json` and edit (real config is gitignored).

---

## 5. Absolute path only for `server_upload_path`

**User:** `server_upload_path` will be absolute path for server.

**What we did:**
- `server_upload_path` must start with `/` (validated at startup).
- Removed home-directory / `~/` resolution; path is used as-is.
- Example mapping: local `material/docs/readme.txt` → `/your/absolute/path/docs/readme.txt` on server.

**User config example (actual path from a successful test run):**

```json
"server_upload_path": "/home/st78326/domains/st78326.ispot.cc/public_html/hkc"
```

---

## 6. `Missing dependency: paramiko` when using system Python

**User:**

```powershell
PS C:\Users\aaa\source\testupload> python .\upload.py
Missing dependency: paramiko
Install with: pip install paramiko
```

**Cause:** `python upload.py` used system Python; paramiko was installed only in `.venv`.

**Fix:**
1. Dependencies already in `.venv` via `pip install -r requirements.txt`.
2. Updated `upload.py` to **re-exec with `.venv\Scripts\python.exe`** when the project venv exists, so plain `python upload.py` works.

**Ways to run:**

```powershell
python .\upload.py          # auto-uses .venv if present
.\upload.bat
.\.venv\Scripts\python.exe .\upload.py
```

**Verify:** Test run with system `python` connected successfully, found 11 files, used server path `/home/st78326/domains/st78326.ispot.cc/public_html/hkc`, exit code 0.

---

## Summary of project layout

| Path | Purpose |
|------|---------|
| `upload.py` | Resumable SFTP uploader for `material/` |
| `upload_config.json` | SSH credentials + `server_upload_path` (gitignored) |
| `upload_config.example.json` | Template for config |
| `config.json` | Per-file upload status (gitignored) |
| `material/` | Local files to upload (contents gitignored) |
| `.venv/` | Python dependencies (gitignored) |
| `requirements.txt` | pip dependencies |
| `upload.bat` / `upload.sh` | Launchers using venv when available |

---

## Security note

Do not commit `upload_config.json` (contains password). It is listed in `.gitignore`.
