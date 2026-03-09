# bot/utils/keyboards.py
from telegram import InlineKeyboardButton as Btn, InlineKeyboardMarkup as Mk
from bot.utils.constants import TMDB_GENRES, MOOD_MAP, KEY_TYPES, E_ARROW_L, E_ARROW_R


def _contact_row() -> list[list[Btn]]:
    return [[Btn("📞 Live Chat", callback_data="start_chat")]]


def movie_detail_kb(movie_id: int, in_watchlist: bool = False) -> Mk:
    save_text = "✅ Saved" if in_watchlist else "📥 Save"
    save_data = f"wl_remove:{movie_id}" if in_watchlist else f"wl_add:{movie_id}"
    return Mk([
        [
            Btn("🎥 Trailer", callback_data=f"trailer:{movie_id}"),
            Btn(save_text, callback_data=save_data),
            Btn("✅ Watched", callback_data=f"watched_add:{movie_id}"),
        ],
        [
            Btn("📺 Stream", callback_data=f"where:{movie_id}"),
            Btn("🔍 Similar", callback_data=f"similar:{movie_id}"),
            Btn("🧠 Explain", callback_data=f"explain_menu:{movie_id}"),
        ],
        [Btn("🔔 Alert", callback_data=f"alert_add:{movie_id}")],
    ])


def search_results_kb(movies: list[dict]) -> Mk:
    buttons = []
    for m in movies[:8]:
        mid = m["id"]
        title = m.get("title", "?")[:28]
        year = m.get("release_date", "")[:4]
        rating = m.get("vote_average", 0)
        label = f"🎬 {title} ({year}) ⭐{rating:.0f}" if year else f"🎬 {title}"
        buttons.append([Btn(label, callback_data=f"movie:{mid}")])
    return Mk(buttons)


def rating_kb(movie_id: int) -> Mk:
    return Mk([
        [
            Btn("★ 2", callback_data=f"rate:{movie_id}:2"),
            Btn("★ 4", callback_data=f"rate:{movie_id}:4"),
            Btn("★ 6", callback_data=f"rate:{movie_id}:6"),
        ],
        [
            Btn("★ 8", callback_data=f"rate:{movie_id}:8"),
            Btn("★ 9", callback_data=f"rate:{movie_id}:9"),
            Btn("🌟 10", callback_data=f"rate:{movie_id}:10"),
        ],
        [Btn("📝 Review", callback_data=f"review:{movie_id}")],
    ])


def confirm_kb(action: str, data: str) -> Mk:
    return Mk([
        [
            Btn("✅ Confirm", callback_data=f"confirm:{action}:{data}"),
            Btn("❌ Cancel", callback_data="cancel"),
        ]
    ])


def mood_kb() -> Mk:
    moods = list(MOOD_MAP.keys())
    rows = [moods[i:i + 3] for i in range(0, len(moods), 3)]
    buttons = [
        [Btn(m, callback_data=f"mood:{m}") for m in row]
        for row in rows
    ]
    return Mk(buttons)


def genre_select_kb(selected: set[int] | None = None) -> Mk:
    selected = selected or set()
    buttons: list[list[Btn]] = []
    row: list[Btn] = []
    for gid, name in sorted(TMDB_GENRES.items(), key=lambda x: x[1]):
        prefix = "✅ " if gid in selected else ""
        row.append(Btn(f"{prefix}{name}", callback_data=f"genre_sel:{gid}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([Btn("✅ Done", callback_data="genre_done")])
    return Mk(buttons)


def recommend_type_kb() -> Mk:
    return Mk([
        [Btn("😊 By Mood", callback_data="rec_type:mood")],
        [Btn("🎭 By Genre", callback_data="rec_type:genre")],
        [Btn("🎬 Similar", callback_data="rec_type:similar")],
        [Btn("🎲 Surprise!", callback_data="rec_type:surprise")],
    ])


def explain_type_kb(movie_id: int) -> Mk:
    return Mk([
        [
            Btn("📖 Plot", callback_data=f"explain:plot:{movie_id}"),
            Btn("🔚 Ending", callback_data=f"explain:ending:{movie_id}"),
        ],
        [
            Btn("🔍 Hidden", callback_data=f"explain:hidden:{movie_id}"),
            Btn("👤 Characters", callback_data=f"explain:chars:{movie_id}"),
        ],
    ])


def priority_kb(movie_id: int) -> Mk:
    return Mk([
        [
            Btn("🔴 High", callback_data=f"pri:{movie_id}:HIGH"),
            Btn("🟡 Medium", callback_data=f"pri:{movie_id}:MED"),
            Btn("🟢 Low", callback_data=f"pri:{movie_id}:LOW"),
        ]
    ])


def pagination_kb(prefix: str, page: int, total_pages: int) -> Mk:
    buttons: list[Btn] = []
    if page > 1:
        buttons.append(Btn(f"{E_ARROW_L} Prev", callback_data=f"{prefix}:page:{page - 1}"))
    buttons.append(Btn(f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        buttons.append(Btn(f"Next {E_ARROW_R}", callback_data=f"{prefix}:page:{page + 1}"))
    return Mk([buttons]) if buttons else Mk([])


def pro_upgrade_kb() -> Mk:
    return Mk([
        [
            Btn("🔑 Redeem", callback_data="redeem_prompt"),
            Btn("👑 Plans", callback_data="view_plans"),
        ],
        *_contact_row(),
    ])


def admin_dashboard_kb() -> Mk:
    return Mk([
        [
            Btn("📊 Stats", callback_data="adm:stats"),
            Btn("🔑 Gen Key", callback_data="adm:genkey"),
            Btn("📦 Bulk", callback_data="adm:bulkkeys"),
        ],
        [
            Btn("🔍 Key Info", callback_data="adm:keyinfo"),
            Btn("👤 Lookup", callback_data="adm:userlookup"),
            Btn("📢 Broadcast", callback_data="adm:broadcast"),
        ],
        [
            Btn("📋 List", callback_data="adm:listkeys:1"),
            Btn("🚫 Revoke", callback_data="adm:revoke"),
            Btn("🤖 AI Status", callback_data="adm:aistatus"),
        ],
        [
            Btn("🖥️ Backend", callback_data="adm:backend"),
            Btn("💬 Chats", callback_data="adm:chats"),
        ],
    ])


def random_filter_kb() -> Mk:
    genres = [
        (28, "Action"), (35, "Comedy"), (18, "Drama"),
        (27, "Horror"), (878, "Sci-Fi"), (10749, "Romance"),
        (53, "Thriller"), (16, "Animation"),
    ]
    rows: list[list[Btn]] = []
    row: list[Btn] = []
    for gid, name in genres:
        row.append(Btn(name, callback_data=f"random_genre:{gid}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([Btn("🎲 Any Genre", callback_data="random_genre:any")])
    return Mk(rows)


def alert_list_kb(alerts: list, page: int, total_pages: int) -> Mk:
    buttons: list[list[Btn]] = []
    for a in alerts:
        title = a.movie_title[:25]
        buttons.append([Btn(f"❌ {title}", callback_data=f"alert_rm:{a.tmdb_movie_id}")])
    nav: list[Btn] = []
    if page > 1:
        nav.append(Btn(E_ARROW_L, callback_data=f"alerts:page:{page - 1}"))
    if page < total_pages:
        nav.append(Btn(E_ARROW_R, callback_data=f"alerts:page:{page + 1}"))
    if nav:
        buttons.append(nav)
    return Mk(buttons)


def no_results_kb() -> Mk:
    return Mk([
        [
            Btn("🔍 Try Again", callback_data="back_main"),
            Btn("🎲 Random", callback_data="random_genre:any"),
        ],
        *_contact_row(),
    ])


def rate_limit_kb() -> Mk:
    return Mk([
        [
            Btn("👑 Upgrade", callback_data="view_plans"),
            Btn("📞 Live Chat", callback_data="start_chat"),
        ],
    ])


def back_button(callback_data: str = "back_main") -> Mk:
    return Mk([[Btn(f"{E_ARROW_L} Back", callback_data=callback_data)]])


def support_admin_kb(chat_id: int, user_id: int) -> Mk:
    return Mk([
        [
            Btn("💬 Reply", callback_data=f"sr:{chat_id}:{user_id}"),
            Btn("💰 Plans", callback_data=f"sp:{user_id}"),
            Btn("🎁 Gift", callback_data=f"sg:{user_id}"),
        ],
        [
            Btn("👤 Info", callback_data=f"si:{user_id}"),
            Btn("📜 History", callback_data=f"sh:{chat_id}"),
            Btn("⏸ Hold", callback_data=f"shold:{chat_id}:{user_id}"),
        ],
        [
            Btn("⚡ Quick", callback_data=f"sq:{chat_id}:{user_id}"),
            Btn("✅ Close", callback_data=f"sc:{chat_id}:{user_id}"),
            Btn("🚫 Block", callback_data=f"sb:{chat_id}:{user_id}"),
        ],
    ])