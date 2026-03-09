# bot/services/ai_service.py
import logging
import json
import asyncio
import re
import httpx
from datetime import datetime, timezone
from bot.config import get_settings
from bot.models.engine import redis_client
from bot import ExternalAPIError

logger = logging.getLogger(__name__)
_s = get_settings()
_http: httpx.AsyncClient | None = None
_providers: list[tuple[str, int, object]] = []
_initialized = False


def _get_http() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(
            timeout=httpx.Timeout(45.0, connect=10.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
    return _http


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def _get_usage(name: str) -> int:
    return int(await redis_client.get(f"ai_usage:{name}:{_today()}") or 0)


async def _incr_usage(name: str) -> None:
    key = f"ai_usage:{name}:{_today()}"
    pipe = redis_client.pipeline()
    pipe.incr(key)
    pipe.expire(key, 90000)
    await pipe.execute()


def _extract_json(text: str) -> list | dict:
    text = text.strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if m:
            text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for sc, ec in [("[", "]"), ("{", "}")]:
        si = text.find(sc)
        ei = text.rfind(ec)
        if si != -1 and ei > si:
            candidate = text[si : ei + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                fixed = re.sub(r",\s*([}\]])", r"\1", candidate)
                try:
                    return json.loads(fixed)
                except json.JSONDecodeError:
                    continue
    return json.loads(text)


async def _gemini(system: str, user: str) -> str:
    client = _get_http()
    body: dict = {
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1500},
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    resp = await client.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
        params={"key": _s.GEMINI_API_KEY},
        json=body,
    )
    resp.raise_for_status()
    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError("Empty Gemini response")
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise ValueError("No content parts")
    return parts[0].get("text", "")


async def _groq(system: str, user: str) -> str:
    client = _get_http()
    resp = await client.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {_s.GROQ_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": 1500,
            "temperature": 0.7,
        },
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


async def _openrouter(system: str, user: str) -> str:
    client = _get_http()
    resp = await client.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {_s.OPENROUTER_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "meta-llama/llama-3.3-70b-instruct:free",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": 1500,
            "temperature": 0.7,
        },
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


async def _mistral(system: str, user: str) -> str:
    client = _get_http()
    resp = await client.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {_s.MISTRAL_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "mistral-small-latest",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": 1500,
            "temperature": 0.7,
        },
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


async def _cohere(system: str, user: str) -> str:
    client = _get_http()
    resp = await client.post(
        "https://api.cohere.com/v1/chat",
        headers={"Authorization": f"Bearer {_s.COHERE_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "command-r-plus",
            "message": user,
            "preamble": system,
            "temperature": 0.7,
            "max_tokens": 1500,
        },
    )
    resp.raise_for_status()
    return resp.json()["text"]


async def _huggingface(system: str, user: str) -> str:
    client = _get_http()
    prompt = f"<s>[INST] {system}\n\n{user} [/INST]"
    resp = await client.post(
        "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3",
        headers={"Authorization": f"Bearer {_s.HUGGINGFACE_API_KEY}"},
        json={
            "inputs": prompt,
            "parameters": {"max_new_tokens": 1500, "temperature": 0.7, "return_full_text": False},
        },
    )
    if resp.status_code == 503:
        raise ValueError("HuggingFace model loading")
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list) and data:
        return data[0].get("generated_text", "")
    return str(data)


async def _cloudflare(system: str, user: str) -> str:
    client = _get_http()
    resp = await client.post(
        f"https://api.cloudflare.com/client/v4/accounts/{_s.CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/meta/llama-3.1-70b-instruct",
        headers={"Authorization": f"Bearer {_s.CLOUDFLARE_API_KEY}", "Content-Type": "application/json"},
        json={
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": 1500,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("result", {}).get("response", "")


def _init_providers():
    global _providers, _initialized
    if _initialized:
        return
    _initialized = True
    if _s.GEMINI_API_KEY:
        _providers.append(("gemini", 1500, _gemini))
    if _s.GROQ_API_KEY:
        _providers.append(("groq", 14400, _groq))
    if _s.OPENROUTER_API_KEY:
        _providers.append(("openrouter", 200, _openrouter))
    if _s.MISTRAL_API_KEY:
        _providers.append(("mistral", 500, _mistral))
    if _s.COHERE_API_KEY:
        _providers.append(("cohere", 33, _cohere))
    if _s.HUGGINGFACE_API_KEY:
        _providers.append(("huggingface", 1000, _huggingface))
    if _s.CLOUDFLARE_API_KEY and _s.CLOUDFLARE_ACCOUNT_ID:
        _providers.append(("cloudflare", 10000, _cloudflare))
    logger.info(f"AI service: {len(_providers)} providers → {[p[0] for p in _providers]}")


async def _chat(system: str, user: str, cache_key: str | None = None, ttl: int = 3600) -> str:
    if cache_key:
        cached = await redis_client.get(cache_key)
        if cached:
            return cached
    _init_providers()
    if not _providers:
        raise ExternalAPIError("AI (no providers configured)")
    errors = []
    for name, limit, call_fn in _providers:
        usage = await _get_usage(name)
        if usage >= limit:
            continue
        for attempt in range(2):
            try:
                result = await call_fn(system, user)
                if result and result.strip():
                    await _incr_usage(name)
                    if cache_key and ttl:
                        await redis_client.setex(cache_key, ttl, result)
                    return result
                raise ValueError("Empty response")
            except Exception as e:
                errors.append(f"{name}:{e}")
                logger.warning(f"AI {name} attempt {attempt + 1} failed: {e}")
                if attempt == 0:
                    await asyncio.sleep(1)
                break
    logger.error(f"All AI providers failed: {errors}")
    raise ExternalAPIError("AI")


async def get_recommendations(
    preferences: dict,
    watched_titles: list[str],
    mode: str = "general",
    extra_context: str = "",
) -> list[dict]:
    liked_genres = preferences.get("liked_genres", {})
    genre_str = ", ".join(
        v.get("name", k) for k, v in list(liked_genres.items())[:8]
    ) if liked_genres else "various"
    watched_str = ", ".join(watched_titles[:20]) if watched_titles else "none yet"
    avg_rating = preferences.get("avg_rating", "N/A")
    system = (
        "You are a world-class film recommender. Return exactly 5 movie recommendations as a JSON array. "
        "Each object must have: {\"title\": str, \"year\": int, \"reason\": str (1 sentence why), \"confidence\": int (60-99)}. "
        "Only return valid JSON array, no markdown, no explanation, no extra text."
    )
    user = (
        f"Mode: {mode}\n"
        f"Favorite genres: {genre_str}\n"
        f"Average rating given: {avg_rating}\n"
        f"Already watched: {watched_str}\n"
        f"Additional context: {extra_context}\n"
        "Recommend 5 movies they haven't watched. Diverse but matching their taste. "
        "Prioritize highly-rated critically acclaimed films."
    )
    text = await _chat(system, user)
    try:
        result = _extract_json(text)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, ValueError):
        logger.error(f"Failed to parse recommendations: {text[:200]}")
        return []


async def explain_movie(
    title: str, year: str, overview: str, explain_type: str = "plot",
) -> str:
    type_prompts = {
        "plot": "Provide a detailed plot summary including major story beats. Spoiler warning included.",
        "ending": "Explain the ending in detail. What happened and why. Include any ambiguous elements.",
        "hidden": "Reveal hidden details, Easter eggs, symbolism, and things most viewers miss.",
        "chars": "Provide deep character analysis for the main characters. Motivations, arcs, development.",
    }
    type_titles = {
        "plot": "📖 Full Plot Summary",
        "ending": "🔚 Ending Explained",
        "hidden": "🔍 Hidden Details & Easter Eggs",
        "chars": "👤 Character Analysis",
    }
    system = (
        "You are an expert film critic and analyst. Provide detailed, engaging movie analysis. "
        "Use clear formatting with sections. Be thorough but concise. Always start with a spoiler warning if needed."
    )
    user = (
        f"Movie: {title} ({year})\nOverview: {overview}\n\n"
        f"Task: {type_prompts.get(explain_type, type_prompts['plot'])}\n\n"
        f"Format your response starting with: {type_titles.get(explain_type, '📖 Analysis')}\n"
        "Keep it under 1200 characters for Telegram."
    )
    cache_key = f"ai:explain:{title.lower()}:{year}:{explain_type}"
    return await _chat(system, user, cache_key, 86400)


async def mood_recommendations(
    mood: str, preferences: dict, watched_titles: list[str],
) -> list[dict]:
    liked_genres = preferences.get("liked_genres", {})
    genre_str = ", ".join(
        v.get("name", k) for k, v in list(liked_genres.items())[:5]
    ) if liked_genres else "various"
    watched_str = ", ".join(watched_titles[:15]) if watched_titles else "none"
    system = (
        "You are a mood-based movie recommender. Return exactly 5 movies as a JSON array. "
        "Each: {\"title\": str, \"year\": int, \"reason\": str, \"confidence\": int (60-99)}. "
        "Only valid JSON array, no extra text."
    )
    user = (
        f"User mood: {mood}\n"
        f"They like: {genre_str}\n"
        f"Already watched: {watched_str}\n"
        "Recommend 5 perfect movies for this mood. Not already watched."
    )
    text = await _chat(system, user)
    try:
        result = _extract_json(text)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, ValueError):
        logger.error(f"Failed to parse mood recs: {text[:200]}")
        return []


async def compare_movies(movie_a: dict, movie_b: dict) -> str:
    system = (
        "You are a film critic comparing two movies. Be concise, engaging, witty. "
        "Give a brief comparison and declare a winner with reasoning. Under 800 characters."
    )
    user = (
        f"Movie A: {movie_a.get('title')} ({movie_a.get('release_date', '')[:4]})\n"
        f"Rating: {movie_a.get('vote_average')}, Genres: {movie_a.get('genres_text', '')}\n"
        f"Overview: {movie_a.get('overview', '')[:200]}\n\n"
        f"Movie B: {movie_b.get('title')} ({movie_b.get('release_date', '')[:4]})\n"
        f"Rating: {movie_b.get('vote_average')}, Genres: {movie_b.get('genres_text', '')}\n"
        f"Overview: {movie_b.get('overview', '')[:200]}\n\n"
        "Compare them and pick a winner."
    )
    cache_key = f"ai:compare:{movie_a.get('id')}:{movie_b.get('id')}"
    return await _chat(system, user, cache_key, 86400)


async def analyze_taste(watch_history: list[dict]) -> dict:
    if not watch_history:
        return {}
    movies_str = "\n".join(
        f"- {m.get('title', '?')} (rated {m.get('rating', 'N/A')}/10, genres: {m.get('genres', 'N/A')})"
        for m in watch_history[:30]
    )
    system = (
        "Analyze the user's watching history and return a JSON object with: "
        '{"preferred_genres": [str], "preferred_themes": [str], "preferred_eras": [str], '
        '"viewing_pattern": str, "recommendation_strategy": str}. Only valid JSON.'
    )
    user = f"Watch history:\n{movies_str}\n\nAnalyze their taste profile."
    cache_key = f"ai:taste:{hash(movies_str) % 10**8}"
    text = await _chat(system, user, cache_key, 43200)
    try:
        result = _extract_json(text)
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, ValueError):
        logger.error(f"Failed to parse taste analysis: {text[:200]}")
        return {}


async def get_status() -> dict:
    _init_providers()
    status = {}
    for name, limit, _ in _providers:
        usage = await _get_usage(name)
        remaining = max(0, limit - usage)
        status[name] = {
            "usage": usage,
            "limit": limit,
            "remaining": remaining,
            "exhausted": usage >= limit,
        }
    total_remaining = sum(v["remaining"] for v in status.values())
    total_limit = sum(v["limit"] for v in status.values())
    status["_total"] = {"remaining": total_remaining, "limit": total_limit}
    return status


async def close():
    global _http
    if _http and not _http.is_closed:
        await _http.aclose()
        _http = None