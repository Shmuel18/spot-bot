# Deliverables — RDR2-Spot v1.1

זו רשימת הדרישות והמשימות שכל מפתח צריך לספק בסוף הפיתוח (או כנקודת בדיקה):

## A) תשתית וחיבור לבינאנס
1. עבודה עם Binance Spot בלבד (USDT pairs).
2. חיבור API אסינכרוני: `python-binance AsyncClient` + שימוש ב-`asyncio`.
3. תמיכה ב-2 מצבים: DRY_RUN ו-LIVE.
4. טעינת Secrets רק מ-`.env`.

## B) קונפיג חיצוני (Config)
- `config.yaml` עם ולידציה (`pydantic`).
- רשימת פרמטרים כפי שמפורט באפיון (timeframe, dip threshold, SMA length, TP percent, DCA, ועוד).

## C) סריקה ואיתותים (Signal Engine)
- סריקה לפי Universe rules.
- חישוב תנאי כניסה והוצאה לאור של сигнали.

## D) מנוע עסקאות (Trade Manager)
- פתיחת BUY, הצבת TP כ-LIMIT SELL על avg_price * 1.025.
- DCA עד 3 שלבים, ביטול TP וקביעת TP חדש לאחר כל DCA.
- מניעת כפילויות.

## E) ניהול סיכונים
- Precision Guard, Exposure Guard, Daily Loss Limit, Cooldown.

## F) State + Database
- SQLite + aiosqlite, טבלאות `trades` ו-`orders`.
- State Machine לכל עסק.
- שחזור מצב מלא אחרי ריסטארט.

## G) ניטור ולוגים
- Logging לקובץ + קונסול.
- Telegram alerts (כניסה, DCA, סגירה, שגיאות, דוח יומי).

## H) טיפול בשגיאות ועמידות
- Retry + Backoff, reconnect, stop-after-errors.

## I) בדיקות וקריטריוני קבלה
- Dry-run חובה.
- קריטריוני קבלה: אין כפילויות עסקאות, אין חריגות exposure, precision תקין, restart שומר על המצב.

## תוצרים סופיים
- Repo מסודר עם README.
- `config.yaml.example` ו-`.env.example`.
- Docs (SRS + Deliverables).
- הוראות התקנה והרצה.
