@echo off
echo ==================================================
echo   MarketFlow Integrated Strategy Alerts
echo ==================================================
echo.
echo Running strategy scanners... (Please wait)
echo.

python -u kr_market\engine\integrated_job.py

echo.
echo ==================================================
echo   Task completed.
echo ==================================================
pause
