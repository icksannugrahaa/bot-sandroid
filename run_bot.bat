@echo off
:: Pindah ke direktori bot dimana file batch ini berada
cd /d "%~dp0"

:: Cek apakah folder log sudah ada, kalau belum buat
if not exist "log" mkdir "log"

:: Gunakan Python dari venv jika ada, jika tidak gunakan python global
echo Menjalankan Sandroid OpenWA Bot...
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" bot.py
) else (
    echo [WARNING] venv\Scripts\python.exe tidak ditemukan! Menggunakan python global...
    python bot.py
)
pause
