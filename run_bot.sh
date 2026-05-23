#!/bin/bash
# Pindah ke direktori bot
cd "$(dirname "$0")"

# Buat folder log jika belum ada
mkdir -p log

# Jalankan bot
echo "Menjalankan Sandroid OpenWA Bot..."
./venv/bin/python bot.py
