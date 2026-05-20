@echo off
setlocal
cd /d "%~dp0"

echo Starting upload...
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
    echo Upload exited with code %EXIT_CODE%.
)

endlocal & exit /b %EXIT_CODE%
