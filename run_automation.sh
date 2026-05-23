#!/bin/bash
# Pindah ke direktori bot
cd "$(dirname "$0")"

mkdir -p log

# Jalankan skrip automation
./venv/bin/python automation.py >> log/cron.log 2>&1
