@echo off
setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch_bs_portal.ps1" %*
set "BS_PORTAL_EXIT=%ERRORLEVEL%"

if not "%BS_PORTAL_EXIT%"=="0" (
    echo.
    echo B.S. Portal launcher exited with code %BS_PORTAL_EXIT%.
    echo Review the message above. No database migrations were applied automatically.
    pause
)

exit /b %BS_PORTAL_EXIT%
