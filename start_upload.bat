@echo off
setlocal
cd /d "%~dp0"

echo Starting upload...
echo   Exit codes: 0=ok, 1=auth, 2=SSH lost, 3=network down, 4=stall timeout
echo   Progress is saved in config.sqlite on exit — restart to resume.
echo.

if exist "%~dp0upload.bat" (
    call "%~dp0upload.bat"
    set "EXIT_CODE=%ERRORLEVEL%"
) else if exist "%~dp0upload.py" (
    if exist "%~dp0.venv\Scripts\python.exe" (
        set "PYTHON=%~dp0.venv\Scripts\python.exe"
    ) else (
        set "PYTHON=python"
    )
    "%PYTHON%" "%~dp0upload.py"
    set "EXIT_CODE=%ERRORLEVEL%"
) else (
    echo upload.bat and upload.py not found in %~dp0
    set "EXIT_CODE=1"
)

if not "%EXIT_CODE%"=="0" (
    echo.
    if "%EXIT_CODE%"=="3" (
        echo Network unavailable. Progress saved — fix connection and run again.
    ) else if "%EXIT_CODE%"=="4" (
        echo No data transferred within stall_timeout_seconds. Progress saved — run again.
    ) else if "%EXIT_CODE%"=="2" (
        echo SSH session lost. Progress saved — run again to resume.
    ) else (
        echo Upload exited with code %EXIT_CODE%.
    )
)

endlocal & exit /b %EXIT_CODE%
