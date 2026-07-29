@echo off
setlocal
cd /d "%~dp0\.."
echo.
echo Strikers Statcast Importer
echo ==========================
python tools\import_statcast.py %*
if errorlevel 1 (
  echo.
  echo Import failed. Review the message above.
  pause
  exit /b 1
)
echo.
echo Statcast import finished successfully.
pause
