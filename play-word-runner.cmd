@echo off
cd /d "%~dp0"
python desktop.py
if errorlevel 1 (
  echo Khong mo duoc Word Runner. Hay kiem tra Python da duoc cai dat.
  pause
)
