# bot/utils/formatters.py
from datetime import datetime, timezone
from bot.utils.constants import (
    E_MOVIE, E_STAR, E_CLOCK, E_GLOBE, E_TROPHY, E_CHECK, E_CHART,
    E_CALENDAR, E_CROWN, E_SPARKLE, E_FIRE, E_FILM, E_TV,
    E_LIST, E_PERSON, E_KEY, E_BRAIN, E_WARN, E_PHONE, E_WAIT,
    E_ROBOT, E_SEARCH, E_INFO, E_PARTY, E_CLAP, E_POPCORN, E_SHIELD,
    E_SERVER,
    LINE, LINE_LIGHT, BADGE_PRO, BADGE_HOT, BADGE_NEW, BADGE_TOP,
    TMDB_GENRES, MILESTONES, FREE_LIMITS,
)
from bot.utils.validators import sanitize_html


def section(title: str) -> str:
    return f"─── ◆ {title} ◆ ───"


def progress_bar(current: int, maximum: int, length: int = 10) -> str:
    if maximum <= 0:
        return "░" * length
    filled = min(length, int((current / maximum) * length))
    return "█" * filled + "░" * (length - filled)


def star_rating(score: float) -> str:
    stars = min(5, max(0, int(score / 2)))
    return "★" * stars + "☆" * (5 - stars)


def format_votes(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return f"{count:,}"


def genre_tags(genre_ids: list[int] | None = None, genres: list[dict] | None = None) -> str:
    names = []
    if genre_ids:
        names = [TMDB_GENRES.get(g, "") for g in genre_ids if g in TMDB_GENRES]
    elif genres:
        names = [g["name"] for g in genres]
    return " ".join(f"⌈{n}⌋" for n in names[:4] if n) if names else ""


def movie_badges(movie: dict) -> str:
    badges = []
    rating = movie.get("vote_average", 0)
    popularity = movie.get("popularity", 0)
    release = movie.get("release_date", "")
    if rating >= 8.0:
        badges.append(BADGE_TOP)
    if popularity >= 100:
        badges.append(BADGE_HOT)
    if release:
        try:
            rd = datetime.strptime(release, "%Y-%m-%d")
            if (datetime.now() - rd).days <= 90:
                badges.append(BADGE_NEW)
        except ValueError:
            pass
    return " ".join(badges[:2])


def format_movie_card(movie: dict) -> str:
    title = sanitize_html(movie.get("title", "Unknown"))
    year = movie.get("release_date", "")[:4] or "?"
    rating = movie.get("vote_average", 0)
    votes = movie.get("vote_count", 0)
    overview = sanitize_html(movie.get("overview", "No overview available."))
    if len(overview) > 350:
        overview = overview[:347] + "..."

    tags = genre_tags(movie.get("genre_ids"), movie.get("genres"))
    badges = movie_badges(movie)
    stars = star_rating(rating)

    runtime = movie.get("runtime")
    lang = (movie.get("original_language") or "").upper()
    rd = movie.get("release_date", "")

    meta_parts = []
    if runtime:
        meta_parts.append(f"{E_CLOCK} <b>{runtime}m</b>")
    if rd:
        meta_parts.append(f"{E_CALENDAR} {rd}")
    if lang:
        meta_parts.append(f"{E_GLOBE} {lang}")
    meta_line = " · ".join(meta_parts)

    badge_str = f"  {badges}" if badges else ""

    text = f"{E_MOVIE} <b>{title}</b> ({year}){badge_str}\n"
    text += f"{LINE}\n"
    text += f"{E_STAR} <b>{rating:.1f}</b>/10 {stars} · 🗳 {format_votes(votes)}\n"
    if tags:
        text += f"🎭 {tags}\n"
    if meta_line:
        text += f"{meta_line}\n"
    text += f"\n{section('Synopsis')}\n"
    text += overview
    return text


def format_movie_short(movie: dict) -> str:
    title = sanitize_html(movie.get("title", "Unknown"))
    year = movie.get("release_date", "")[:4] or "?"
    rating = movie.get("vote_average", 0)
    return f"{E_MOVIE} <b>{title}</b> ({year}) · {E_STAR} {rating:.1f}"


def format_movie_credits(credits: dict) -> str:
    cast = credits.get("cast", [])[:5]
    directors = [c for c in credits.get("crew", []) if c.get("job") == "Director"]
    lines = [section("Cast & Crew")]
    if directors:
        names = ", ".join(sanitize_html(d["name"]) for d in directors[:2])
        lines.append(f"🎥 <b>ᴅɪʀᴇᴄᴛᴏʀ:</b> {names}")
    if cast:
        names = ", ".join(sanitize_html(a["name"]) for a in cast)
        lines.append(f"🌟 <b>ᴄᴀsᴛ:</b> {names}")
    return "\n".join(lines) if len(lines) > 1 else ""


def format_comparison(a: dict, b: dict) -> str:
    def score(m):
        return m.get("vote_average", 0) * 0.6 + min(m.get("popularity", 0) / 100, 40) * 0.4

    sa, sb = score(a), score(b)
    winner = a if sa >= sb else b
    wt = sanitize_html(winner.get("title", ""))

    def side(m, color):
        t = sanitize_html(m.get("title", "Unknown"))
        y = m.get("release_date", "")[:4] or "?"
        r = m.get("vote_average", 0)
        v = m.get("vote_count", 0)
        rt = m.get("runtime", "?")
        tags = genre_tags(m.get("genre_ids"), m.get("genres"))
        return (
            f"{color} <b>{t}</b> ({y})\n"
            f"   {E_STAR} <b>{r:.1f}</b>/10 · 🗳 {format_votes(v)}\n"
            f"   {E_CLOCK} {rt}m · {tags}"
        )

    return (
        f"{E_TROPHY} <b>MOVIE SHOWDOWN</b>\n"
        f"{LINE}\n\n"
        f"{side(a, '🔵')}\n\n"
        f"          ⚔️  VS  ⚔️\n\n"
        f"{side(b, '🔴')}\n\n"
        f"{LINE}\n"
        f"{E_TROPHY} <b>Winner: {wt}</b> {E_SPARKLE}"
    )


def format_watchlist_item(item, idx: int) -> str:
    pri = {"HIGH": "🔴", "MED": "🟡", "LOW": "🟢"}.get(item.priority.value, "⚪")
    title = sanitize_html(item.movie_title)
    return f"{idx}. {pri} <b>{title}</b> (ID: {item.tmdb_movie_id})"


def format_watched_item(item, idx: int) -> str:
    title = sanitize_html(item.movie_title)
    rating_str = f"{E_STAR} {item.user_rating}/10" if item.user_rating else "unrated"
    date_str = item.watched_at.strftime("%b %d") if item.watched_at else ""
    return f"{idx}. {E_FILM} <b>{title}</b> — {rating_str} · {date_str}"


def format_stats(stats: dict) -> str:
    total = stats.get("total_watched", 0)
    avg = stats.get("avg_rating", 0)
    genre_bars = stats.get("genre_bars", "No data yet.")
    best = sanitize_html(stats.get("best", "N/A"))
    month = stats.get("active_month", "N/A")

    return (
        f"{E_CHART} <b>YOUR STATS</b>\n"
        f"{LINE}\n\n"
        f"{E_FILM} Movies watched: <b>{total}</b>\n"
        f"{E_STAR} Average rating: <b>{avg:.1f}</b>/10\n"
        f"{E_CROWN} Highest rated: <b>{best}</b>\n"
        f"{E_CALENDAR} Most active: <b>{month}</b>\n\n"
        f"{section('Genre Breakdown')}\n"
        f"{genre_bars}"
    )


def build_genre_bars(genre_counts: dict[str, int], top_n: int = 8) -> str:
    if not genre_counts:
        return "No data yet."
    sorted_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:top_n]
    max_count = sorted_genres[0][1] if sorted_genres else 1
    lines = []
    for gid, count in sorted_genres:
        name = TMDB_GENRES.get(int(gid), f"#{gid}")
        bar = progress_bar(count, max_count, 10)
        lines.append(f"  {name}: {bar} {count}")
    return "\n".join(lines)


def format_streaming(data: dict | None, country: str = "US") -> str:
    if not data:
        return (
            f"{E_TV} <b>No streaming info available</b>\n\n"
            f"💡 Try checking JustWatch for this title"
        )
    lines = [
        f"{E_TV} <b>WHERE TO WATCH</b> ({country})",
        LINE,
    ]
    sections_data = [
        ("flatrate", "📺 Stream"),
        ("rent", "💲 Rent"),
        ("buy", "🛒 Buy"),
    ]
    found = False
    for key, label in sections_data:
        providers = data.get(key, [])
        if providers:
            names = ", ".join(p.get("provider_name", "?") for p in providers[:5])
            lines.append(f"  {label}: {names}")
            found = True
    if not found:
        lines.append("  No options found for this region.")
    return "\n".join(lines)


def format_recommendation_list(movies: list[dict], title: str = "Recommendations") -> str:
    lines = [
        f"{E_BRAIN} <b>{title}</b>",
        LINE,
    ]
    for i, m in enumerate(movies, 1):
        t = sanitize_html(m.get("title", "Unknown"))
        y = m.get("release_date", "")[:4] or "?"
        r = m.get("vote_average", 0)
        conf = m.get("confidence")
        reason = m.get("ai_reason", "")
        conf_str = f" · {conf}% match" if conf else ""
        lines.append(f"\n{i}. {E_MOVIE} <b>{t}</b> ({y})")
        lines.append(f"   {E_STAR} {r:.1f}{conf_str}")
        if reason:
            lines.append(f"   💡 <i>{sanitize_html(reason[:80])}</i>")
    return "\n".join(lines)


def format_key_info(key) -> str:
    status_dot = {
        "UNUSED": "🟢", "USED": "🔵", "EXPIRED": "🟡", "REVOKED": "🔴",
    }.get(key.status.value, "⚪")
    return (
        f"{E_KEY} <b>KEY INFO</b>\n"
        f"{LINE}\n\n"
        f"Key: <code>{key.key}</code>\n"
        f"Type: <b>{key.key_type}</b> ({key.duration_days}d)\n"
        f"Status: {status_dot} <b>{key.status.value}</b>\n"
        f"Batch: {key.batch_name or 'N/A'}\n"
        f"{LINE_LIGHT}\n"
        f"Created: {key.created_at.strftime('%Y-%m-%d %H:%M') if key.created_at else 'N/A'}\n"
        f"Redeemed by: {key.redeemed_by_user_id or 'N/A'}\n"
        f"Redeemed at: {key.redeemed_at.strftime('%Y-%m-%d %H:%M') if key.redeemed_at else 'N/A'}"
    )


def format_user_info(user) -> str:
    tier_badge = BADGE_PRO if user.subscription_tier.value == "PRO" else ""
    expires = user.subscription_expires_at.strftime("%Y-%m-%d") if user.subscription_expires_at else "N/A"
    joined = user.created_at.strftime("%Y-%m-%d") if user.created_at else "N/A"
    admin_str = f"{E_CROWN} Admin" if user.is_admin else ""
    return (
        f"{E_PERSON} <b>USER INFO</b> {tier_badge}\n"
        f"{LINE}\n\n"
        f"🆔 <code>{user.telegram_id}</code>\n"
        f"Name: {sanitize_html(user.display_name)}\n"
        f"Username: @{user.username or 'N/A'}\n"
        f"{LINE_LIGHT}\n"
        f"Plan: <b>{user.subscription_tier.value}</b>\n"
        f"Expires: {expires}\n"
        f"Joined: {joined}\n"
        f"{admin_str}"
    )


def format_pro_status(user, usage: dict, wl_count: int) -> str:
    expires = user.subscription_expires_at.strftime("%Y-%m-%d") if user.subscription_expires_at else "N/A"
    days_left = 0
    if user.subscription_expires_at:
        days_left = max(0, (user.subscription_expires_at - datetime.now(timezone.utc)).days)
    return (
        f"{E_CROWN} <b>PRO ACTIVE</b> {BADGE_PRO}\n"
        f"{LINE}\n\n"
        f"Expires: <b>{expires}</b> ({days_left}d left)\n\n"
        f"{section('Usage Today')}\n"
        f"  {E_SEARCH} Searches: {usage.get('search', 0)} (unlimited)\n"
        f"  {E_BRAIN} Recommends: {usage.get('recommend', 0)} (unlimited)\n"
        f"  {E_ROBOT} Explains: {usage.get('explain', 0)} (unlimited)\n"
        f"  {E_LIST} Watchlist: {wl_count} (unlimited)"
    )


def format_free_status(usage: dict, wl_count: int) -> str:
    s_cur, s_max = usage.get("search", 0), FREE_LIMITS["search"]
    r_cur, r_max = usage.get("recommend", 0), FREE_LIMITS["recommend"]
    e_cur, e_max = usage.get("explain", 0), FREE_LIMITS["explain"]
    w_cur, w_max = wl_count, FREE_LIMITS["watchlist"]
    return (
        f"{E_INFO} <b>FREE PLAN</b>\n"
        f"{LINE}\n\n"
        f"{section('Usage Today')}\n"
        f"  {E_SEARCH} Searches:   {progress_bar(s_cur, s_max)} {s_cur}/{s_max}\n"
        f"  {E_BRAIN} Recommends: {progress_bar(r_cur, r_max)} {r_cur}/{r_max}\n"
        f"  {E_ROBOT} Explains:   {progress_bar(e_cur, e_max)} {e_cur}/{e_max}\n"
        f"  {E_LIST} Watchlist:  {progress_bar(w_cur, w_max)} {w_cur}/{w_max}\n\n"
        f"{LINE_LIGHT}\n"
        f"{E_CROWN} Upgrade to Pro for unlimited access!"
    )


def format_admin_stats(
    total_users: int, pro_users: int,
    key_stats: dict, daily: dict, ai_status: dict,
    backend: dict | None = None,
) -> str:
    ai_total = ai_status.get("_total", {})
    ai_rem = ai_total.get("remaining", 0)
    ai_lim = max(ai_total.get("limit", 1), 1)
    ai_pct = (ai_rem / ai_lim) * 100

    lines = [
        f"{E_SHIELD} <b>ADMIN DASHBOARD</b>",
        LINE,
        "",
        section("Users"),
        f"  👥 Total: <b>{total_users}</b>",
        f"  {E_CROWN} Pro: <b>{pro_users}</b>",
        "",
        section("License Keys"),
        f"  🟢 Unused: <b>{key_stats.get('UNUSED', 0)}</b>",
        f"  🔵 Used: <b>{key_stats.get('USED', 0)}</b>",
        f"  🟡 Expired: <b>{key_stats.get('EXPIRED', 0)}</b>",
        f"  🔴 Revoked: <b>{key_stats.get('REVOKED', 0)}</b>",
        f"  {E_CHART} Total: <b>{key_stats.get('TOTAL', 0)}</b>",
        "",
    ]

    if backend:
        db_dot = "🟢" if backend.get("db") else "🔴"
        redis_dot = "🟢" if backend.get("redis") else "🔴"
        tmdb_dot = "🟢" if backend.get("tmdb") else "🔴"
        lines.extend([
            section("Backend"),
            f"  {db_dot} DB: {backend.get('db_ms', '?')}ms",
            f"  {redis_dot} Redis: {backend.get('redis_ms', '?')}ms",
            f"  {tmdb_dot} TMDB: {backend.get('tmdb_ms', '?')}ms",
            "",
        ])

    lines.extend([
        section("AI Capacity"),
        f"  {E_ROBOT} {progress_bar(ai_rem, ai_lim)} {ai_pct:.0f}%",
        f"  Remaining: {ai_rem}/{ai_lim}",
        "",
        section("Today"),
        f"  📨 Commands: <b>{daily.get('total_commands', 0)}</b>",
        f"  {E_PERSON} Active: <b>{daily.get('unique_users', 0)}</b>",
    ])

    return "\n".join(lines)


def format_backend_status(backend: dict) -> str:
    def status_line(name: str, ok: bool, latency: int | None = None) -> str:
        dot = "🟢" if ok else "🔴"
        lat = f" {latency}ms" if latency else ""
        return f"  {dot} <b>{name}</b>{lat}"

    lines = [
        f"{E_SERVER} <b>BACKEND STATUS</b>",
        LINE,
        "",
        section("Services"),
        status_line("PostgreSQL", backend.get("db", False), backend.get("db_ms")),
        status_line("Redis", backend.get("redis", False), backend.get("redis_ms")),
        "",
        section("External APIs"),
        status_line("TMDB", backend.get("tmdb", False), backend.get("tmdb_ms")),
        status_line("YouTube", backend.get("youtube", False), backend.get("youtube_ms")),
        status_line("Streaming", backend.get("streaming", False)),
        "",
        section("DB Pool"),
        f"  Size: {backend.get('db_pool_size', '?')}",
        f"  Checked out: {backend.get('db_pool_checked', '?')}",
        "",
        section("Redis"),
        f"  Connections: {backend.get('redis_connections', '?')}",
        f"  Memory: {backend.get('redis_memory', '?')}",
    ]
    return "\n".join(lines)


def format_no_results(query: str = "") -> str:
    q = sanitize_html(query)
    search_text = f'Can\'t find "<b>{q}</b>" 🙈\n\n' if q else "Can't find that 🙈\n\n"
    return (
        f"{E_SEARCH} <b>Nothing Found</b>\n\n"
        f"{search_text}"
        "💡 Check spelling or try the English title"
    )


def check_milestone(count: int) -> str | None:
    if count in MILESTONES:
        return (
            f"{E_PARTY} <b>MILESTONE!</b>\n"
            f"{LINE}\n\n"
            f"You've watched <b>{count}</b> movies! {E_CLAP}\n"
            f"Keep going! {E_POPCORN}"
        )
    return None