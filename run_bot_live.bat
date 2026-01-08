@echo off
cd /d "%~dp0"
set FORCE_PRICE_CACHE_HEALTHY=1
set TELEGRAM_ENABLED=0
set FORCE_LIVE=1
python -u -m bot.main > bot.log 2> bot.err
