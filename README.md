<!-- <div dir="rtl" align="right">

# 🤖✨ RDR2-Spot — Binance Spot Bot ✨🤖

**Mean Reversion + DCA | Risk Management | SQLite | Telegram Alerts**

<p align="right">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-blue" />
  <img alt="Binance" src="https://img.shields.io/badge/Exchange-Binance%20Spot-yellow" />
  <img alt="Async" src="https://img.shields.io/badge/Async-asyncio-7D3CFF" />
  <img alt="DB" src="https://img.shields.io/badge/DB-SQLite-0A7" />
  <img alt="License" src="https://img.shields.io/badge/License-TBD-lightgrey" />
</p>

> ⚠️ **אזהרה:** מסחר כרוך בסיכון. הפרויקט הזה הוא כלי תוכנה. שימוש בלייב הוא באחריותך בלבד.
> מומלץ להתחיל ב־`DRY_RUN`/סביבת בדיקה, עם סכומים קטנים, ולהוסיף בקרות הגנה לפני מעבר ללייב.

---

## 👋 מה זה הפרויקט?

**RDR2-Spot** הוא בוט מסחר אוטומטי ל־**Binance Spot** שמנסה לנצל ירידות קצרות טווח (דיפים) באמצעות אסטרטגיית **Mean Reversion**.
במידת הצורך הוא מוסיף מדרגות **DCA** (מיצוע), ומנהל את העסקאות דרך חוקים ברורים של סיכון, תיעוד והתרעות.

---

## ✨ יכולות עיקריות

- ✅ **Spot בלבד (ללא מינוף)**
- ✅ כניסה לפי **Mean Reversion**
- ✅ **DCA** עם טריגר ירידה ומקסימום מדרגות
- ✅ **Take Profit** לכל עסקה
- ✅ תיעוד עסקאות ב־**SQLite** + מצב (State)
- ✅ **Recovery** לאחר ריסט (מבוסס DB/State)
- ✅ **Telegram Alerts** (אופציונלי)
- ✅ הפרדת הגדרות: `.env` (סודות) + `config.yaml` (חוקים)

---

## ⚙️ Tech Stack

<p align="right">
  <img alt="Python" src="https://img.shields.io/badge/Python-🐍-blue" />
  <img alt="Asyncio" src="https://img.shields.io/badge/Asyncio-⚡-7D3CFF" />
  <img alt="Binance API" src="https://img.shields.io/badge/Binance%20API-📈-yellow" />
  <img alt="SQLite" src="https://img.shields.io/badge/SQLite-🗄️-0A7" />
  <img alt="Telegram" src="https://img.shields.io/badge/Telegram-📨-2CA5E0" />
</p>

---

## 🧱 מבנה הפרויקט

```text
spot-bot/
├─ bot/
│  ├─ exchange/          # שירותי Binance / עטיפות API
│  ├─ logic/             # אסטרטגיה, DCA, trade manager
│  ├─ risk/              # מגבלות סיכון וחישובים
│  ├─ state/             # שמירת מצב ריצה
│  ├─ database/          # SQLite: טבלאות, CRUD
│  ├─ notifications/     # Telegram / התראות
│  ├─ utils/             # retry, helpers, לוגים
│  └─ main.py            # entrypoint
├─ config/
│  └─ config.yaml.example
├─ docs/
│  ├─ RDR2-Spot-SRS.md
│  └─ Deliverables.md
├─ .env.example
└─ README.md
```

---

## ✅ דרישות מקדימות

- Python **3.10+** (מומלץ 3.11)
- חשבון Binance + יצירת API Key/Secret
- הרשאות מומלצות ל־API:
  - ✅ Read
  - ✅ Spot Trading
  - ❌ Withdrawals (להשאיר כבוי)

---

## 🚀 התקנה והרצה (Quickstart)

### 1) שיכפול הריפו

```bash
git clone https://github.com/Shmuel18/spot-bot.git
cd spot-bot
```

### 2) יצירת סביבה והתקנת תלויות

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

pip install -U pip
pip install -r requirements.txt
```

> אם אין אצלך `requirements.txt`, מומלץ להוסיף. אפשר גם לעבור ל־`pyproject.toml`.

### 3) יצירת `.env` (סודות)

```bash
cp .env.example .env
```

מלא ערכים (דוגמה):

```env
BINANCE_API_KEY=...
BINANCE_API_SECRET=...

DRY_RUN=true
ENV=prod

TELEGRAM_BOT_TOKEN=...   # אופציונלי
TELEGRAM_CHAT_ID=...     # אופציונלי
```

### 4) יצירת `config.yaml` (חוקים)

```bash
cp config/config.yaml.example config/config.yaml
```

### 5) הרצה

```bash
python bot/main.py
```

---

## 🛠️ קונפיגורציה (config.yaml) — דגשים חשובים

- `dca_trigger` מומלץ להיות **אחוז חיובי** (למשל `3.5`)
- הגדל/הקטן:
  - `position_size`
  - `tp_percent`
  - `max_dca_levels`
  - `max_positions`
  - `cooldown_seconds`
  - מגבלות חשיפה (`exposure_*`) + `daily_loss_limit`

> טיפ: אל תעבור ללייב לפני שהכללים באמת נאכפים בפועל (לא רק קיימים בקובץ).

---

## 🔐 אבטחה

- ❌ לא מעלים `.env` לגיט
- ודא ש־`.gitignore` כולל:

```gitignore
.env
bot/.env
*.db
__pycache__/
.venv/
```

> אם `.env` עלה בטעות לגיטהאב פעם — החלף מפתחות מיד.

---

## 🧪 מצבי עבודה

- **DRY_RUN** — סימולציה (מומלץ להתחיל כאן)
- **LIVE** — מסחר אמיתי בבינאנס

---

## 📊 DB / Recovery

הבוט מתעד עסקאות ב־SQLite כדי:

- לשמור היסטוריית פעילות
- להחזיר מצב לאחר ריסט
- לזהות אי־תאמות בין state לבין exchange (כדאי לחזק)

---

## 🗺️ Roadmap

- [ ] ניטור TP רציף + טיפול ב־CANCEL/EXPIRE
- [ ] חישוב NLV מלא בספוט (על בסיס free+locked מהחשבון)
- [ ] Paper Trading / Backtest
- [ ] Dashboard סטטוס
- [ ] CI (Lint + Tests) ב־GitHub Actions
- [ ] Rate-limit handling מתקדם

---

## 🤝 תרומה לפרויקט

1. Fork
2. Branch חדש
3. Commitים ברורים
4. PR עם תיאור + בדיקות (אם יש)

---

## 📬 יצירת קשר

אם בא לך לשפר יחד, להוסיף פיצ׳רים או לעשות review — פתח Issue / שלח הודעה.

</div> -->
<div dir="rtl" align="right">

# 🤖 BOT SPOT — Binance Spot Trading Bot (Mean Reversion + DCA)

בוט מסחר אוטומטי ל־**Binance Spot** המבוסס על:

- **Mean Reversion**: כניסה אחרי "דיפ" ביחס למחיר פתיחה + מתחת ל־SMA
- **DCA**: מיצועים לפי טריגר ירידה
- **TP (Take Profit)**: פקודת מכירה ברווח לכל עסקה
- **SQLite** לתיעוד ו־**Recovery** אחרי ריסט
- **Telegram Alerts** (אופציונלי)

> ⚠️ **אזהרה:** מסחר כרוך בסיכון. הפרויקט הזה הוא תוכנה בלבד. שימוש בלייב הוא באחריותך.

---

## ✨ מה הבוט עושה בפועל?

### 1) סריקה וסינון סימבולים

- מושך את כל הזוגות מול **USDT**
- מסנן לפי `min_24h_volume`
- מסיר זוגות שחוסמים ב־`blacklist`

### 2) תנאי כניסה (Signal)

לכל סימבול:

- מחשב SMA לפי `sma_length` ו־`timeframe` (עם קאש ל־5 דקות)
- מושך קנדל אחרון ובודק:
  - אחוז שינוי מה־Open של הקנדל האחרון קטן/שווה ל־`dip_threshold` (שלילי)
  - המחיר הנוכחי קטן מה־SMA

### 3) פתיחת עסקה

- מחשב גודל פוזיציה לפי `position_size_percent` מתוך USDT חופשי
- בודק מינימום Notional של הבורסה
- פותח `MARKET BUY` (או מדמה אם `dry_run=true`)
- מציב `LIMIT SELL` ל־TP לפי `tp_percent`

### 4) ניטור עסקאות פתוחות

- בודק האם ה־TP התמלא (בלייב לפי סטטוס הזמנה, וב־dry_run לפי מחיר שוק)
- אם טריגר DCA מתקיים:
  - מבטל TP ישן (בלייב)
  - קונה תוספת לפי `dca_scales`
  - מחשב ממוצע חדש ומציב TP חדש
- מעדכן DB כדי שהבוט יוכל להתאושש אחרי ריסט

### 5) ניהול סיכון בסיסי

- `max_positions`: לא פותח יותר מדי עסקאות במקביל
- `daily_loss_limit`: אם ה־equity ירד באחוז היומי שהוגדר, מפסיק לפתוח עסקאות חדשות באותו יום

---

## 🧱 מבנה הפרויקט

```text
BOT SPOT/
├─ bot/
│  ├─ main.py                    # מנוע הריצה (TradingEngine)
│  ├─ config_model.py            # מודל Pydantic להגדרות חובה
│  ├─ exchange/
│  │  └─ binance_service.py      # משיכת זוגות/סינון נפח/בדיקת הזמנות
│  ├─ logic/
│  │  ├─ signal_engine.py        # SMA + תנאי כניסה
│  │  ├─ dca_engine.py           # תנאי DCA
│  │  └─ trade_manager.py        # פתיחה/TP/DCA/חישוב equity בסיסי
│  ├─ database/
│  │  ├─ database_service.py     # SQLite CRUD + סכמות
│  │  └─ trades.db               # DB מקומי (מומלץ לא להעלות לגיט)
│  ├─ notifications/
│  │  └─ telegram_service.py     # שליחת התראות לטלגרם
│  └─ utils/
│     └─ retry.py                # retry בסיסי (Binance errors)
├─ config/
│  └─ config.yaml                # פרמטרים של אסטרטגיה/סיכון
├─ tests/                        # pytest (async)
├─ requirements.txt
├─ .env.example
└─ README.md
```

---

## ✅ דרישות מקדימות

- Python **3.10+** (מומלץ 3.11)
- חשבון Binance + API Key/Secret
- הרשאות API מומלצות:
  - ✅ Read
  - ✅ Spot Trading
  - ❌ Withdrawals (להשאיר כבוי)

---

## 🚀 התקנה

```bash
# מתוך תיקיית הפרויקט
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac/Linux
source .venv/bin/activate

pip install -U pip
pip install -r requirements.txt
```

---

## 🔐 הגדרת סודות (.env)

1. יוצרים קובץ `.env` על בסיס הדוגמה:

```bash
cp .env.example .env
```

2. ממלאים ערכים:

```env
BINANCE_API_KEY=...
BINANCE_API_SECRET=...

TELEGRAM_TOKEN=...       # אופציונלי
TELEGRAM_CHAT_ID=...     # אופציונלי

DATABASE_FILE=bot/database/trades.db
```

> אם אין טלגרם — אפשר להשאיר ריק, אבל אז כדאי לוודא שהקוד לא קורס במקרה של ערכים חסרים.

---

## ⚙️ קונפיגורציה (config/config.yaml)

דוגמה (כמו בריפו):

```yaml
timeframe: 15m
dip_threshold: -3.0
sma_length: 150

tp_percent: 2.5

dca_trigger: 3.5
dca_scales: [1.0, 1.5, 2.0]

position_size_percent: 3
max_positions: 5
min_24h_volume: 5000000
blacklist: [USDC, FDUSD, TUSD, DAI, USDP, UP, DOWN, BULL, BEAR]

cooldown: 30
daily_loss_limit: 5

dry_run: true
sleep_interval: 60
```

דגשים:

- `dip_threshold` הוא **שלילי** (למשל `-3.0` = ירידה של 3% מה־Open).
- `dca_trigger` הוא **חיובי** (למשל `3.5` = ירידה של 3.5% מתחת למחיר הממוצע).
- `dca_scales` אצלך עובד כמכפלה על **הכמות הנוכחית** (יכול לגדול מהר — שים לב).

---

## ▶️ הרצה

```bash
python bot/main.py
```

---

## 🧪 בדיקות

```bash
pytest -q
```

---

## 🧰 הערות חשובות לפרודקשן

מומלץ לפני מעבר ללייב:

- להוסיף `TradingEngine.run()` (לולאת ריצה) אם עדיין חסר/לא קיים
- לוודא טיפול מסודר ב־Rate Limits וב־BinanceAPIException
- לחשב equity אמיתי בספוט (שווי כל הנכסים, לא רק USDT + פוזיציות פתוחות שהבוט "זוכר")
- לוודא ש־DB/State והבורסה מסונכרנים (source of truth ברור)
- להגדיר `.gitignore` כך שלא יעלה:
  - `.env`, `*.db`, `.venv/`, `.pytest_cache/`, `__pycache__/`

---

## 📌 רישיון

לא הוגדר עדיין. אפשר להוסיף MIT / Apache-2.0 וכו׳ לפי הצורך.

</div>
