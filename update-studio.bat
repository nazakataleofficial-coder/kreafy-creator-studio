@echo off
REM Kreafy Creator Studio — safe update (Windows).
REM Usage: update-studio.bat <naya-version-folder-ya-zip>
REM Pehle backup banta hai, phir code badalta hai, phir verify hota hai.
REM Verify fail ho to backup wapas lag jata hai.
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: update-studio.bat ^<naya-version-folder-ya-zip^>
  echo Example: update-studio.bat C:\Downloads\kreafy-creator-studio-test-main.zip
  pause >nul
  exit /b 1
)
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 scripts\update.py --source "%~1"
) else (
  python scripts\update.py --source "%~1"
)
echo.
echo Band karne ke liye koi key dabayen.
pause >nul
