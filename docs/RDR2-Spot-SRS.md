# RDR2-Spot — אפיון מערכת מסחר אוטומטית (SRS) — v1.0

סטטוס: Approved for Development

## 1. מטרה והיקף

### 1.1 מטרה
פיתוח מערכת מסחר אוטומטית לשוק ה-Spot של Binance, הפועלת לפי אסטרטגיית Mean Reversion בתוך מגמה, ללא מינוף וללא שורטים, עם ניהול סיכונים קפדני, שמירת מצב מלאה, ניטור והתראות.

### 1.2 היקף
המערכת תבצע:
- סריקה רציפה של שוק ה-Spot.
- זיהוי מצבי Oversold קצרים בתוך מגמה.
- פתיחת עסקאות קנייה, ניהולן באמצעות DCA ו-TP.
- שליחת התראות.
- שמירת מצב מלא ושחזור לאחר ריסטארט.

המערכת לא תבצע:
- מסחר במינוף / Margin.
- שורטים.
- Borrow / Lending.
- ארביטראז' בין בורסות.

## 2. מונחים
- Entry — קניית פתיחה
- DCA — מיצוע עלויות
- TP — Take Profit
- Exposure — חשיפה כספית
- Universe — סט הסימבולים הנסרקים

## 3. ארכיטקטורה

### 3.1 טכנולוגיה
- שפה: Python 3.10+
- אסינכרון: asyncio
- API: python-binance AsyncClient
- DB: SQLite + aiosqlite
- קונפיג: YAML + dotenv
- ולידציה: pydantic
- התראות: Telegram Bot
- לוגים: logging

### 3.2 מבנה תיקיות (מומלץ)
```
/bot
 ├── config/
 ├── exchange/
 ├── logic/
 ├── risk/
 ├── database/
 ├── notifications/
 ├── state/
 └── main.py
```

## 4. Universe וסריקה

### 4.1 Universe Filter
נסרקים רק:
- זוגות עם USDT.
- לא Stablecoins (USDC, FDUSD, TUSD, DAI, USDP).
- לא Tokens ממונפים (UP/DOWN, BULL/BEAR).
- נפח מסחר 24h ≥ 5M USDT.

### 4.2 Timeframe
- נרות 15 דקות (15m).

## 5. אסטרטגיית מסחר (Trading Logic)

### 5.1 תנאי כניסה
נפתחת עסקה אם מתקיימים כל התנאים:
- שינוי נר 15m ≤ -3.0%
- מחיר < SMA(150)
- אין עסקה פתוחה על הסימבול
- Max positions < 5
- גבולות חשיפה נשמרים

פעולה: קניית Market או Limit אגרסיבי (להחליט לפני פיתוח).

### 5.2 גודל פוזיציה
- גודל בסיסי: 3% מהיתרה
- מקסימום למטבע: 10%
- מקסימום כולל: 40%
- מקסימום עסקאות: 5

### 5.3 Take Profit
- TP = מחיר ממוצע × 1.025
- פקודה: LIMIT SELL

### 5.4 מנגנון מיצוע (DCA)
- טריגר: -3.5% מהממוצע
- שלבים: 3
- סקייל: [1.0, 1.5, 2.0]

תהליך:
1. ביטול TP קיים.
2. קנייה נוספת לפי הסקייל.
3. חישוב ממוצע חדש.
4. הצבת TP חדש.

## 6. ניהול סיכונים
- Max Total Exposure: 40%
- Max Per Symbol: 15%
- Daily Loss Limit: 5% (עצירה מלאה)
- Max Drawdown: 20%
- Cooldown לאחר סגירה: 30 דק'
- Precision Guard: לפי exchangeInfo
- Rate Limit: Backoff אוטומטי

## 7. State Machine
מצבי עסקה:
1. NEW
2. BUY_SENT
3. OPEN
4. TP_PLACED
5. DCA_PENDING
6. CLOSED_PROFIT
7. CLOSED_ABORTED
8. ERROR

כל מעבר מצב נרשם ל-DB.

## 8. Persistence

### 8.1 טבלת trades
- id int
- symbol text
- status text
- avg_price float
- base_qty float
- quote_spent float
- dca_count int
- tp_order_id text
- created_at datetime

### 8.2 טבלת orders
- id int
- trade_id int
- binance_id text
- type text
- price float
- qty float
- status text

## 9. טיפול בשגיאות
- Retry עם Backoff.
- טיפול ב-429 / 418 / ניתוקים.
- עצירה לאחר רצף שגיאות חמור.

## 10. אבטחה
- מפתחות רק ב-.env.
- ללא הרשאות משיכה.
- קריאה + מסחר בלבד.

## 11. ניטור והתראות
- טלגרם: כניסה, מיצוע, יציאה, שגיאה, דו"ח יומי.

## 12. דרישות לא-פונקציונליות
- ביצועים: 100 סימבולים < 5 שניות.
- זמינות: 24/7.
- שחזור: מלא מה-DB.
- תצפית: לוגים + טלגרם.
- בדיקות: Dry-run + Replay.

## 13. קריטריוני קבלה
- אין כפילויות עסקאות.
- אין חריגות חשיפה.
- אין שגיאות דיוק.
- כל מצב משוחזר נכון.

## 14. ניהול גרסאות
- כל שינוי אסטרטגי/תשתיתי מחייב העלאת גרסה.
