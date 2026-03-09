<div align="center">

# 🎬 CineBot

**AI-Powered Telegram Movie Companion**

Your personal movie discovery, tracking & recommendation engine — right inside Telegram.

━━━━━━━━━━━━━━━━━━━━━

[Features](#-features) · [Setup](#-setup) · [Commands](#-commands) · [Plans](#-free-vs-pro) · [Deploy](#-deployment)

━━━━━━━━━━━━━━━━━━━━━

</div>

## ✨ Features

<table>
<tr>
<td width="50%">

### 🔍 Discover
- **Search** — Rich cards with ratings, cast & posters
- **Recommend** — AI picks by mood, genre or taste
- **Random** — Surprise picks with genre filters
- **Mood** — "How are you feeling?" → perfect movie

</td>
<td width="50%">

### 📋 Track
- **Watchlist** — Priority-based save-for-later
- **Watched** — Movie diary with ★ ratings & reviews
- **Stats** — Visual genre bars & milestones
- **Alerts** — Release date notifications

</td>
</tr>
<tr>
<td>

### 🧠 AI-Powered
- **Explain** — Plot, ending, hidden details, characters
- **Compare** — Side-by-side showdown with AI verdict
- **Daily Picks** — Personalized morning suggestions
- **7 AI Providers** — Auto-failover for 100% uptime

</td>
<td>

### 👑 Monetization
- **License Keys** — `CINE-XXXX-XXXX-XXXX-XXXX`
- **Plans** — 1M · 2M · 3M · 6M · 1Y
- **Admin Dashboard** — Generate, revoke, gift, broadcast
- **Support Tickets** — Built-in contact system

</td>
</tr>
</table>

## 🛠 Tech Stack

```
Bot Framework    python-telegram-bot v20+ (async)
Runtime          Python 3.11+
Database         PostgreSQL + SQLAlchemy 2.0 (asyncpg)
Cache            Redis
Movie Data       TMDb API v3
AI Providers     Gemini · Groq · OpenRouter · Mistral · Cohere · HuggingFace · Cloudflare
Trailers         YouTube Data API v3
Streaming        TMDb Watch Providers + RapidAPI fallback
```

## 🚀 Setup

### 1 → Install

```bash
git clone https://github.com/your-repo/cinebot.git
cd cinebot
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 2 → Configure

```bash
cp .env.example .env
```

```env
# Required
BOT_TOKEN=your_bot_token
DATABASE_URL=postgresql://user:pass@localhost:5432/cinebot
TMDB_API_KEY=your_tmdb_key
YOUTUBE_API_KEY=your_youtube_key
STREAMING_API_KEY=your_rapidapi_key
ADMIN_IDS=[123456789]

# AI (at least one)
GEMINI_API_KEY=
GROQ_API_KEY=
OPENROUTER_API_KEY=

# Optional
REDIS_URL=redis://localhost:6379/0
```

### 3 → Initialize

```bash
python scripts/setup_db.py
python scripts/health_check.py
```

### 4 → Run

```bash
python run.py
```

## 📖 Commands

| Command | Description |
|:--------|:------------|
| `/search` `name` | Movie details with full card |
| `/recommend` | AI picks → mood · genre · similar · surprise |
| `/watchlist` | Save-for-later with priorities |
| `/watched` | Log movies · rate · review |
| `/where` `name` | Streaming availability |
| `/compare` `A vs B` | Side-by-side showdown |
| `/explain` `name` | AI plot · ending · hidden · characters |
| `/stats` | Your watching statistics |
| `/alerts` | Release date notifications |
| `/random` | Surprise pick by genre |
| `/mood` | Mood-based recommendations |
| `/redeem` `KEY` | Activate Pro subscription |
| `/pro` | View plan & usage |
| `/contact` `msg` | Message admin support |

> 💡 **Tip:** Just type any movie name — no command needed.

<details>
<summary><b>🛡️ Admin Commands</b></summary>

| Command | Description |
|:--------|:------------|
| `/admin` | Dashboard with stats |
| `/genkey` `TYPE` | Generate single key |
| `/genkeys` `TYPE QTY BATCH` | Bulk generate → `.txt` file |
| `/keyinfo` `KEY` | Key status lookup |
| `/revokekey` `KEY` | Revoke + downgrade user |
| `/listkeys` `[STATUS]` | Filter: UNUSED · USED · EXPIRED · REVOKED |
| `/userlookup` `ID` | User profile lookup |
| `/giftkey` `ID TYPE` | Gift Pro to user |
| `/broadcast` `[all\|pro] msg` | Broadcast message |
| `/aistatus` | AI provider capacity |
| `/tickets` | Support ticket queue |

</details>

## 💎 Free vs Pro

```
Feature              Free          Pro
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Searches/day         ████████░░    Unlimited
                     10/day

Recommendations/day  █████░░░░░    Unlimited
                     5/day

AI Explanations/day  ███░░░░░░░    Unlimited
                     3/day

Watchlist items      ████████░░    Unlimited
                     20 max

Daily suggestions    Limited       ✅ Full
Priority support     ❌            ✅
```

## 📁 Architecture

```
cinebot/
├── run.py                     Entry point + health server
├── scripts/
│   ├── setup_db.py            Database initialization
│   ├── health_check.py        Service diagnostics
│   └── generate_keys.py       CLI key generation
└── bot/
    ├── main.py                App builder · handlers · jobs
    ├── config.py              Pydantic settings
    ├── handlers/              17 handler modules
    ├── services/
    │   ├── ai_service.py      7-provider failover chain
    │   ├── tmdb_service.py    Movie data + caching
    │   ├── recommendation_engine.py
    │   ├── streaming_service.py
    │   ├── youtube_service.py
    │   └── key_service.py     License key logic
    ├── models/                SQLAlchemy ORM + repositories
    ├── middleware/             Rate limits · auth · analytics
    ├── utils/                 Formatters · keyboards · validators
    └── jobs/                  Scheduled tasks
```

## ⏰ Scheduled Jobs

| Job | Schedule | What it does |
|:----|:---------|:-------------|
| Daily Suggestion | `09:00 UTC` | Personalized movie push |
| Release Alerts | Every `6h` | Notify upcoming releases |
| Subscription Expiry | `00:30 UTC` | Warnings + auto-downgrade |

## 🌐 Deployment

```bash
# Polling (development)
python run.py

# Webhook (production)
USE_WEBHOOK=true WEBHOOK_URL=https://your.domain python run.py
```

<details>
<summary><b>Docker</b></summary>

```bash
docker-compose up -d
```

</details>

<details>
<summary><b>Systemd</b></summary>

```bash
sudo cp cinebot.service /etc/systemd/system/
sudo systemctl enable --now cinebot
```

</details>

---

<div align="center">

**Built with** 🐍 Python · 🐘 PostgreSQL · 🔴 Redis · 🎬 TMDb

</div>
