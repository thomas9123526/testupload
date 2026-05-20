@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

if not exist "%~dp0upload.py" (
    powershell -NoProfile -Command "Write-Host 'upload.py not found.' -ForegroundColor Red"
    exit /b 1
)

:loop
echo.
echo === Starting upload.py ===
"%PYTHON%" "%~dp0upload.py"
set "EXIT_CODE=!ERRORLEVEL!"

if !EXIT_CODE!==0 (
    echo.
    powershell -NoProfile -Command "Write-Host 'Auto Upload Is Finished' -ForegroundColor Green"
    exit /b 0
)

if !EXIT_CODE!==130 (
    echo.
    powershell -NoProfile -Command "Write-Host 'Upload interrupted (Ctrl+C). Auto upload stopped.' -ForegroundColor Red"
    exit /b 130
)

call :print_error !EXIT_CODE!
call :read_interval
call :countdown !INTERVAL!
goto loop

:print_error
set "CODE=%~1"
if "%CODE%"=="1" (
    powershell -NoProfile -Command "Write-Host 'Upload failed: authentication error (exit 1). Check upload_config.json credentials.' -ForegroundColor Red"
) else if "%CODE%"=="2" (
    powershell -NoProfile -Command "Write-Host 'Upload failed: SSH connection lost (exit 2). Progress saved in config.json.' -ForegroundColor Red"
) else if "%CODE%"=="3" (
    powershell -NoProfile -Command "Write-Host 'Upload failed: network unavailable (exit 3). Progress saved in config.json.' -ForegroundColor Red"
) else if "%CODE%"=="4" (
    powershell -NoProfile -Command "Write-Host 'Upload failed: transfer stalled - no data moved (exit 4). Progress saved in config.json.' -ForegroundColor Red"
) else (
    powershell -NoProfile -Command "Write-Host 'Upload failed with exit code %CODE%. Progress saved in config.json.' -ForegroundColor Red"
)
exit /b 0

:read_interval
set "INTERVAL="
for /f "delims=" %%i in ('"%PYTHON%" "%~dp0read_auto_upload_retry.py"') do set "INTERVAL=%%i"
if not defined INTERVAL set "INTERVAL=300"
echo Retry interval: !INTERVAL!s ^(config.json: auto_upload_retry_seconds^)
exit /b 0

:countdown
set "SECONDS=%~1"
powershell -NoProfile -Command ^
  "$n = [int]$env:SECONDS; for ($i = $n; $i -ge 1; $i--) { Write-Host ('Retrying upload in {0} seconds...' -f $i) -ForegroundColor Yellow; Start-Sleep -Seconds 1 }"
exit /b 0
