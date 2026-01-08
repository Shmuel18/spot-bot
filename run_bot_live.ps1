$env:FORCE_PRICE_CACHE_HEALTHY = '1'
$env:TELEGRAM_ENABLED = '0'
$env:FORCE_LIVE = '1'
Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Definition)
python -u -m bot.main > bot.log 2> bot.err
