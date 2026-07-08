@echo off
chcp 65001 > nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo ====================================================
echo   장중 원석 발굴 (Intraday Gem Hunter) 자동 스캐너
echo   (09:00 ~ 15:20 동안 5분 간격으로 실행됩니다)
echo ====================================================

:loop
echo [%time%] 스캐닝 시작...
python kr_market\engine\intraday_gem_scanner.py

echo.
echo [%time%] 스캐닝 완료. 다음 스캔까지 5분(300초) 대기합니다...
C:\Windows\System32\timeout.exe /t 300 /nobreak > nul
echo.

goto loop
