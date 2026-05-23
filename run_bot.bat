@echo off
:: Pindah ke direktori bot dimana file batch ini berada
cd /d "%~dp0"

:: Cek apakah folder log sudah ada, kalau belum buat
if not exist "log" mkdir "log"

:: Gunakan Python dari venv secara eksplisit untuk menjalankan bot
echo Menjalankan Sandroid OpenWA Bot...
"venv\Scripts\python.exe" bot.py
pause
