@echo off
chcp 65001 >nul
cd /d D:\INFORUN\HoDoo\Part7
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
python -X utf8 daily_update.py >> logs\daily_bat.log 2>&1
