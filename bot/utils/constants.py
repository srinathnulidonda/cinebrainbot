# bot/utils/constants.py

E_MOVIE = "🎬"
E_STAR = "⭐"
E_FIRE = "🔥"
E_HEART = "❤️"
E_CLOCK = "🕐"
E_GLOBE = "🌐"
E_TROPHY = "🏆"
E_LOCK = "🔒"
E_KEY = "🔑"
E_CHECK = "✅"
E_CROSS = "❌"
E_WARN = "⚠️"
E_INFO = "ℹ️"
E_SEARCH = "🔍"
E_LIST = "📋"
E_CHART = "📊"
E_BELL = "🔔"
E_DICE = "🎲"
E_BRAIN = "🧠"
E_POPCORN = "🍿"
E_CLAP = "👏"
E_PARTY = "🎉"
E_CROWN = "👑"
E_SPARKLE = "✨"
E_FILM = "🎞"
E_TV = "📺"
E_MONEY = "💰"
E_CALENDAR = "📅"
E_PIN = "📌"
E_ARROW_R = "→"
E_ARROW_L = "←"
E_UP = "⬆️"
E_DOWN = "⬇️"
E_REFRESH = "🔄"
E_SEND = "📤"
E_PERSON = "👤"
E_PEOPLE = "👥"
E_GEAR = "⚙️"
E_ROBOT = "🤖"
E_GEM = "💎"
E_BOLT = "⚡"
E_PHONE = "📞"
E_SHIELD = "🛡️"
E_WAIT = "⏳"
E_SERVER = "🖥️"

# Mobile-friendly separators
LINE = "─ ─ ─ ─ ─ ─ ─ ─"
LINE_LIGHT = "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"

BADGE_PRO = "「👑 ᴘʀᴏ」"
BADGE_HOT = "「🔥 ʜᴏᴛ」"
BADGE_NEW = "「✨ ɴᴇᴡ」"
BADGE_TOP = "「⭐ ᴛᴏᴘ」"

TMDB_GENRES = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy",
    80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family",
    14: "Fantasy", 36: "History", 27: "Horror", 10402: "Music",
    9648: "Mystery", 10749: "Romance", 878: "Sci-Fi", 10770: "TV Movie",
    53: "Thriller", 10752: "War", 37: "Western",
}

MOOD_MAP = {
    "😄 Happy": [35, 10751, 16, 10402],
    "😢 Sad": [18, 10749],
    "😱 Scared": [27, 53],
    "🤔 Think": [99, 36, 9648],
    "💑 Love": [10749, 18, 35],
    "😂 Funny": [35, 16],
}

FREE_LIMITS = {
    "search": 10,
    "explain": 3,
    "recommend": 5,
    "watchlist": 20,
}

PRO_LIMITS = {
    "search": 999999,
    "explain": 999999,
    "recommend": 999999,
    "watchlist": 999999,
}

KEY_TYPES = {
    "1M": {"label": "1 Month", "days": 30},
    "2M": {"label": "2 Months", "days": 60},
    "3M": {"label": "3 Months", "days": 90},
    "6M": {"label": "6 Months", "days": 180},
    "1Y": {"label": "1 Year", "days": 365},
}

MILESTONES = [1, 5, 10, 25, 50, 100, 250, 500, 1000]

MSG_WELCOME = (
    f"{E_MOVIE} <b>CINEBOT</b> {E_POPCORN}\n"
    f"{LINE}\n"
    "Your AI-powered movie companion\n\n"
    "─── ◆ Discover ◆ ───\n"
    f"{E_SEARCH} /search — Find any movie\n"
    f"{E_BRAIN} /recommend — AI picks for you\n"
    f"{E_DICE} /random — Surprise me\n"
    "😊 /mood — Match your vibe\n\n"
    "─── ◆ Library ◆ ───\n"
    f"{E_LIST} /watchlist — Save for later\n"
    f"{E_CHECK} /watched — Movie diary\n"
    f"{E_CHART} /stats — Your stats\n\n"
    "─── ◆ Explore ◆ ───\n"
    f"{E_TV} /where — Where to stream\n"
    f"{E_TROPHY} /compare — Head to head\n"
    f"{E_BRAIN} /explain — AI deep dive\n"
    f"{E_BELL} /alerts — Release alerts\n\n"
    "─── ◆ Account ◆ ───\n"
    f"{E_KEY} /redeem — Activate Pro\n"
    f"{E_CROWN} /pro — Your plan\n"
    f"{E_PHONE} /contact — Reach us\n\n"
    f"{LINE_LIGHT}\n"
    f"💡 Type any movie name to search instantly"
)

MSG_HELP = (
    f"{E_INFO} <b>CINEBOT HELP</b>\n"
    f"{LINE}\n\n"
    "─── ◆ Search & Discovery ◆ ───\n"
    f"  {E_SEARCH} /search <code>name</code> — Movie details\n"
    f"  {E_BRAIN} /recommend — Personalized picks\n"
    f"  {E_DICE} /random — Random suggestion\n"
    "  😊 /mood — Mood-based picks\n\n"
    "─── ◆ Your Library ◆ ───\n"
    f"  {E_LIST} /watchlist — Watch-later list\n"
    f"  {E_CHECK} /watched — Movie diary\n"
    f"  {E_CHART} /stats — Viewing stats\n\n"
    "─── ◆ Movie Intel ◆ ───\n"
    f"  {E_TV} /where <code>name</code> — Streaming info\n"
    f"  {E_TROPHY} /compare <code>A vs B</code> — Compare\n"
    f"  {E_BRAIN} /explain <code>name</code> — AI analysis\n\n"
    "─── ◆ Account ◆ ───\n"
    f"  {E_KEY} /redeem <code>KEY</code> — Activate Pro\n"
    f"  {E_CROWN} /pro — Plan & usage\n"
    f"  {E_BELL} /alerts — Release alerts\n"
    f"  {E_PHONE} /contact — Support\n\n"
    f"{LINE_LIGHT}\n"
    "💡 <b>Inline:</b> Type <code>@YourBot movie</code> in any chat"
)

MSG_ONBOARDING_GENRES = (
    f"{E_MOVIE} <b>Let's personalize your experience!</b>\n"
    f"{LINE}\n\n"
    "Pick your favorite genres (at least 2):"
)

MSG_RATE_LIMITED = (
    f"{E_WAIT} <b>Slow down!</b>\n\n"
    "Try again in 10 seconds."
)

MSG_PRO_REQUIRED = (
    f"{E_LOCK} <b>PRO Feature</b>\n"
    f"{LINE}\n\n"
    f"{E_SPARKLE} Unlimited searches & recs\n"
    f"{E_SPARKLE} Unlimited explains\n"
    f"{E_SPARKLE} Unlimited watchlist\n"
    f"{E_SPARKLE} Priority support\n\n"
    f"{E_KEY} Use /redeem or {E_PHONE} /contact"
)

MSG_KEY_REDEEMED = (
    f"{E_PARTY} <b>KEY REDEEMED!</b>\n"
    f"{LINE}\n\n"
    f"{E_CROWN} Plan: <b>PRO</b>\n"
    f"{E_CALENDAR} Duration: <b>{{duration}}</b>\n"
    f"{E_WAIT} Expires: <b>{{expires}}</b>\n\n"
    f"{E_SPARKLE} Unlimited access unlocked! {E_POPCORN}"
)

MSG_EXPIRY_WARNING = (
    f"{E_WARN} <b>SUBSCRIPTION EXPIRING</b>\n"
    f"{LINE}\n\n"
    f"{E_WAIT} Expires in <b>{{days}} day(s)</b>\n"
    f"{E_CALENDAR} Date: <b>{{date}}</b>\n\n"
    f"{E_KEY} /redeem to extend\n"
    f"{E_PHONE} /contact to renew"
)

MSG_EXPIRED = (
    f"{E_INFO} <b>Subscription Expired</b>\n"
    f"{LINE}\n\n"
    "Your Pro plan has ended.\n"
    "You're now on the Free plan.\n\n"
    f"{E_KEY} /redeem a new key to reactivate\n"
    f"{E_PHONE} /contact for help"
)

MSG_NO_RESULTS = (
    f"{E_SEARCH} <b>Nothing Found</b>\n\n"
    "Can't find that 🙈\n\n"
    "💡 Check spelling or try the English title"
)

MSG_WATCHLIST_EMPTY = (
    f"{E_LIST} <b>Nothing here yet</b> — let's fix that! {E_MOVIE}\n\n"
    f"Use /search to find movies to save"
)

MSG_WATCHED_EMPTY = (
    f"{E_FILM} <b>No movies logged yet</b>\n\n"
    "Mark a movie as watched after you see it!\n"
    f"Use /search to get started {E_POPCORN}"
)

MSG_MILESTONE = (
    f"{E_PARTY} <b>MILESTONE!</b>\n"
    f"{LINE}\n\n"
    f"You've watched <b>{{count}}</b> movies! {E_CLAP}\n"
    "Keep the streak going! 🍿"
)