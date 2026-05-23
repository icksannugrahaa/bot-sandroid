#!/bin/bash
# Pindah ke direktori bot
cd "$(dirname "$0")"

mkdir -p log

# Jalankan pengecekan nightly
./venv/bin/python automation.py --nightly >> log/cron.log 2>&1
