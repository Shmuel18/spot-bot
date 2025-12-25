<!-- <div dir="rtl" align="right">

# 🤖 Spot Bot — RDR2-Spot
בוט מסחר אוטומטי ל־**Binance Spot** המבוסס על אסטרטגיית **Mean Reversion + DCA** עם ניהול סיכונים, תיעוד עסקאות (SQLite) והתראות טלגרם.

> ⚠️ **אזהרה חשובה:** זהו פרויקט תוכנה למסחר. שימוש בלייב הוא באחריותך בלבד. מומלץ להתחיל ב־`DRY_RUN`/סביבת בדיקה, עם סכומים קטנים, ולהוסיף בקרות הגנה לפני כל מעבר ללייב.

---

## ✨ יכולות עיקריות
- **מסחר Spot בלבד** (ללא מינוף).
- **Mean Reversion**: כניסות על “דיפים” בתוך מסגרת חוקים.
- **DCA (ממוצעים)**: הוספת פקודות לפי טריגר ירידה מוגדר.
- **Take Profit**: יציאה ב־TP מוגדר לכל עסקה.
- **DB (SQLite)**: שמירת עסקאות + אפשרות התאוששות לאחר ריסט (`recovery`).
- **התראות Telegram**: עדכונים על כניסות/יציאות/שגיאות (בהתאם להגדרות).
- **הפרדת קונפיג**:
  - סודות ב־`.env`
  - חוקים/פרמטרים ב־`config.yaml`

---

## 🧱 מבנה הפרויקט (הסבר מהיר)
- `bot/` — קוד המקור (ריצה, לוגיקה, exchange, DB, utils).
- `config/` — קבצי דוגמה לקונפיג.
- `docs/` — מסמכי אפיון (SRS) ותוצרים.
- `.env.example` — דוגמה למשתני סביבה.
- `config/config.yaml.example` — דוגמה לקונפיג.

---

## ✅ דרישות מקדימות
- Python 3.10+ (מומלץ 3.11)
- חשבון Binance עם **API Key** ו־**API Secret**
- הרשאות API:
  - ✅ Read (קריאה)
  - ✅ Spot & Margin Trading (ל־Spot Trading)
  - ❌ **לא** לאפשר Withdraws (מומלץ להשאיר כבוי)

---

## 🚀 התקנה והרצה (Quickstart)

### 1) שכפול הפרויקט
```bash
git clone https://github.com/Shmuel18/spot-bot.git
cd spot-bot
```

### 2) יצירת סביבה והתקנת תלויות
אם יש `requirements.txt`:
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

אם יש `pyproject.toml`:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install .
```

### 3) יצירת `.env`
העתק את הדוגמה:
```bash
copy .env.example .env
```
או:
```bash
cp .env.example .env
```

מלא את הערכים (דוגמה):
- `BINANCE_API_KEY=...`
- `BINANCE_API_SECRET=...`
- `TELEGRAM_BOT_TOKEN=...` (אופציונלי)
- `TELEGRAM_CHAT_ID=...` (אופציונלי)
- `ENV=prod|test` (לפי הקוד אצלך)
- `DRY_RUN=true|false`

### 4) יצירת `config.yaml`
```bash
copy config\config.yaml.example config\config.yaml
```
או:
```bash
cp config/config.yaml.example config/config.yaml
```

### 5) הרצה
> הפקודה המדויקת תלויה ב־entrypoint בפרויקט. האפשרויות הנפוצות:
```bash
python -m bot
```
או:
```bash
python bot/main.py
```

---

## ⚙️ קונפיגורציה (config.yaml)
הקובץ `config.yaml` הוא “המוח” של החוקים:
- רשימת סימבולים / סינון נפח
- גודל פוזיציה
- TP (%)
- טריגר DCA (%)
- מקסימום מדרגות DCA
- מגבלות סיכון (מומלץ להפעיל): max positions, exposure limits, daily loss

דגשים מומלצים:
- `dca_trigger` צריך להיות **אחוז חיובי** (למשל `3.5` = ירידה של 3.5%).
- להגדיר `max_positions` כדי לא להיפתח על יותר מדי סימבולים.
- להגדיר `cooldown` כדי להימנע מספאם כניסות.

---

## 🔐 אבטחה ו־Secrets
- **לא** מעלים ל־GitHub קובץ `.env`
- ודא ש־`.env` נמצא ב־`.gitignore`
- מומלץ לייצר API Key ייעודי לבוט ולהגביל IP אם אפשר.

---

## 🧪 מצבי עבודה
- **DRY_RUN**: סימולציה (לא שולח פקודות אמת). מומלץ להתחיל כאן.
- **LIVE**: שולח פקודות אמת ל־Binance.

> כדאי להוסיף לוגים ברורים בכל פעולה משמעותית: פתיחה, DCA, TP, ביטולים, שגיאות.

---

## 📦 DB / Recovery
הבוט שומר עסקאות ב־SQLite כדי:
- לשמור היסטוריה
- לבצע `recovery` לאחר ריסט (למשל לבדוק אם TP התמלא)

> מומלץ לוודא שהריצה השוטפת מבצעת ניטור TP בצורה רציפה, לא רק בתחילת הרצה.

---

## 🧰 פיתוח וסטנדרטים (מומלץ)
- `ruff` / `flake8` ללינט
- `black` לפורמט
- `pytest` לטסטים
- GitHub Actions ל־CI בסיסי

---

## 🗺️ Roadmap (רעיונות לשדרוג)
- ניטור TP רציף בלולאה הראשית
- חישוב equity מלא בספוט (כולל שווי נכסים מוחזקים)
- Backtest / Paper Trading
- Dashboard קטן (סטטוס פוזיציות, PnL, חשיפות)
- Rate-limit handling מתקדם ל־Binance API
- ניהול “מצב” עקבי בין DB ל־Exchange (source of truth)

---

## 📄 מסמכים
- `docs/RDR2-Spot-SRS.md` — אפיון מערכת (SRS)
- `docs/Deliverables.md` — תוצרים/דרישות למסירה

---

## 🤝 תרומה לפרויקט
PRs מתקבלים בכיף:
1. Fork
2. Branch חדש
3. Commitים ברורים
4. Pull Request עם תיאור שינוי + בדיקות

---

## 📜 רישיון
עדכן כאן רישיון אם תרצה (MIT / Apache-2.0 / GPL וכו').

</div> -->

<div dir="rtl" align="right">

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

</div>
