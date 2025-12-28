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
<!-- <div dir="rtl" align="right">

# 🤖✨ Spot-Bot — Binance Spot Bot ✨🤖

**Mean Reversion + DCA | Risk Management | SQLite | Telegram Alerts**

<p align="right">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-blue" />
  <img alt="Binance" src="https://img.shields.io/badge/Exchange-Binance%20Spot-yellow" />
  <img alt="Async" src="https://img.shields.io/badge/Async-asyncio-7D3CFF" />
  <img alt="DB" src="https://img.shields.io/badge/DB-SQLite-0A7" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-lightgrey" />
</p>

> ⚠️ **אזהרה:** מסחר כרוך בסיכון. זהו כלי תוכנה. שימוש בלייב הוא באחריותך בלבד.
> מומלץ להתחיל ב־`DRY_RUN`, עם סכומים קטנים, ולהפעיל בקרות סיכון לפני מעבר ללייב.

---

## 👋 מה זה הפרויקט?

**Spot-Bot** הוא בוט מסחר אוטומטי ל־**Binance Spot** שמנסה לנצל ירידות קצרות טווח ("דיפים") לפי אסטרטגיית **Mean Reversion**.
כאשר המחיר ממשיך לרדת — הבוט מוסיף מדרגות **DCA**, מחשב ממוצע חדש, ומעדכן את ה־Take Profit בהתאם.

---

## ✨ יכולות עיקריות

- ✅ Spot בלבד (ללא מינוף)
- ✅ כניסה לפי Mean Reversion (Dip + SMA)
- ✅ DCA מדורג עם טריגר ירידה ומקסימום מדרגות
- ✅ Take Profit אוטומטי לכל עסקה
- ✅ שמירת מצב ב־SQLite + Recovery לאחר ריסט
- ✅ Telegram Alerts (אופציונלי)
- ✅ הפרדת סודות (`.env`) וחוקים (`config.yaml`)

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
│  ├─ exchange/
│  ├─ logic/
│  ├─ risk/
│  ├─ database/
│  ├─ notifications/
│  └─ main.py
├─ config/
│  └─ config.yaml.example
├─ .env.example
└─ README.md
```

</div> -->

<div dir="rtl" align="right">

# 🤖✨ Spot-Bot — Binance Spot Bot ✨🤖

**Mean Reversion + DCA | Risk Management | SQLite | Telegram Alerts**

<p align="right">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-blue" />
  <img alt="Binance" src="https://img.shields.io/badge/Exchange-Binance%20Spot-yellow" />
  <img alt="Async" src="https://img.shields.io/badge/Async-asyncio-7D3CFF" />
  <img alt="DB" src="https://img.shields.io/badge/DB-SQLite-0A7" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-lightgrey" />
</p>

> ⚠️ **אזהרה:** מסחר כרוך בסיכון. זהו כלי תוכנה. שימוש בלייב הוא באחריותך בלבד.  
> מומלץ להתחיל ב־`DRY_RUN`, עם סכומים קטנים, ולהפעיל בקרות סיכון לפני מעבר ללייב.

---

## 👋 מה זה הפרויקט?

**Spot-Bot** הוא בוט מסחר אוטומטי ל־**Binance Spot** שמנסה לנצל ירידות קצרות טווח ("דיפים") לפי אסטרטגיית **Mean Reversion**.  
כאשר המחיר ממשיך לרדת — הבוט מוסיף מדרגות **DCA**, מחשב ממוצע חדש, ומעדכן את ה־Take Profit בהתאם.

---

## ✨ יכולות עיקריות

- ✅ Spot בלבד (ללא מינוף)
- ✅ כניסה לפי Mean Reversion (Dip + SMA)
- ✅ DCA מדורג עם טריגר ירידה ומקסימום מדרגות
- ✅ Take Profit אוטומטי לכל עסקה
- ✅ שמירת מצב ב־SQLite + Recovery לאחר ריסט
- ✅ Telegram Alerts (אופציונלי)
- ✅ הפרדת סודות (`.env`) וחוקים (`config.yaml`)

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
│  ├─ exchange/
│  ├─ logic/
│  ├─ risk/
│  ├─ database/
│  ├─ notifications/
│  └─ main.py
├─ config/
│  └─ config.yaml.example
├─ .env.example
└─ README.md
```

---

## 🚀 התקנה והרצה

```bash
git clone https://github.com/Shmuel18/spot-bot.git
cd spot-bot
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate # Mac/Linux
pip install -r requirements.txt
cp .env.example .env
cp config/config.yaml.example config/config.yaml
python bot/main.py
```

---

## 🔐 משתני סביבה (.env)

```env
BINANCE_API_KEY=...
BINANCE_API_SECRET=...
DRY_RUN=true
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

---

## 🛠️ קונפיגורציה (config.yaml)

- dip_threshold — אחוז ירידה לכניסה
- tp_percent — יעד רווח
- dca_trigger — ירידה להפעלת DCA
- max_ladders — מקסימום מדרגות
- position_size_percent — חשיפה

---

## 🧪 מצבי עבודה

- DRY_RUN=true — סימולציה
- DRY_RUN=false — לייב

---

## 🗺️ Roadmap

- [ ] Backtesting
- [ ] Dashboard
- [ ] CI / Tests
- [ ] Dry-run משופר

---

## 📄 רישיון

MIT

---

## 📬 יצירת קשר

Issue / PR / הודעה בפרטי 🙂

</div>
