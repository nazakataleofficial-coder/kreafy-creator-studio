@echo off
REM Kreafy Creator Studio — one-click launcher (Windows).
REM Double-click karein: backend + frontend start honge aur dashboard
REM browser me khul jayega. Band karne ke liye Ctrl+C dabayen.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 studio\launcher.py %*
) else (
  python studio\launcher.py %*
)
echo.
echo Band ho gaya — window band karne ke liye koi key dabayen.
pause >nul
