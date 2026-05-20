@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

if not exist "%~dp0auto_upload.py" (
    echo auto_upload.py not found.
    exit /b 1
)

"%PYTHON%" "%~dp0auto_upload.py"
set "EXIT_CODE=%ERRORLEVEL%"

endlocal & exit /b %EXIT_CODE%
