@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

for /f %%i in ('"%PYTHON%" "%~dp0read_loop_interval.py"') do set "INTERVAL=%%i"

if not exist "%~dp0start_upload.bat" (
    echo start_upload.bat not found in %~dp0
    exit /b 1
)

echo Loop upload — monitoring start_upload.bat
echo   Retry interval: !INTERVAL!s ^(loop_upload_interval in upload_config.json or config.json^)
echo   Exit 0 = done; non-zero error = wait and retry; Ctrl+C = stop
echo.

:loop
call "%~dp0start_upload.bat"
set "EXIT_CODE=!ERRORLEVEL!"

if !EXIT_CODE!==0 (
    echo.
    echo Upload finished successfully. Loop stopped.
    exit /b 0
)

if !EXIT_CODE!==130 (
    echo.
    echo Interrupted. Loop stopped.
    exit /b 130
)

echo.
echo Upload exited with error code !EXIT_CODE!.
echo Progress saved in config.json. Retrying in !INTERVAL!s ...
timeout /t !INTERVAL! /nobreak >nul
echo.
goto loop
