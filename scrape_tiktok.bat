@echo off
REM One-click TikTok scraper for BAKMA spoilers.
cd /d "%~dp0"

if "%TIKTOK_SESSIONID%"=="" (
    set /p TIKTOK_SESSIONID=Paste your TikTok sessionid cookie (recommended, or Enter to skip): 
)
if "%TIKTOK_SESSIONID%"=="" (
    if "%TIKTOK_MS_TOKEN%"=="" (
        set /p TIKTOK_MS_TOKEN=Paste your TikTok msToken cookie (or press Enter to skip): 
    )
)

echo.
echo Starting TikTok scrape... a browser window may open. Please wait.
echo.
".venv\Scripts\python.exe" scrape_tiktok.py %*

echo.
echo Done. Upload the generated tiktok_bakma_*.csv via the dashboard's "Import CSV" button.
pause
