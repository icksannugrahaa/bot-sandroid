@echo off
:: Pindah ke direktori bot dimana file batch ini berada
cd /d "%~dp0"

:: Cek apakah folder log sudah ada, kalau belum buat
if not exist "log" mkdir "log"

:: Gunakan Python dari venv jika ada, jika tidak gunakan python global
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" automation.py --nightly >> log\cron.log 2>&1
) else (
    python automation.py --nightly >> log\cron.log 2>&1
)
