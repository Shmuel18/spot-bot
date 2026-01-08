$env:FORCE_PRICE_CACHE_HEALTHY = '1'
$env:TELEGRAM_ENABLED = '0'
# הפנייה לנתיב העבודה הנוכחי
Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Definition)
# הרצת הבוט וכתיבת לוגים
python -u -m bot.main > bot.log 2> bot.err
