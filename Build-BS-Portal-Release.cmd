@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0packaging\windows\build_release.ps1" %*
if errorlevel 1 (
  echo.
  echo B.S. Portal release build failed.
  pause
  exit /b 1
)
echo.
echo B.S. Portal release build complete. See release\windows\
pause
