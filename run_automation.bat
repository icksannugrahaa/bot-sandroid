@echo off
:: Pindah ke direktori bot dimana file batch ini berada
cd /d "%~dp0"

:: Cek apakah folder log sudah ada, kalau belum buat
if not exist "log" mkdir "log"

:: Gunakan Python dari venv secara eksplisit
"venv\Scripts\python.exe" automation.py >> log\cron.log 2>&1
