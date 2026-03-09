# bot/utils/validators.py
import re
from bot.utils.constants import KEY_TYPES

KEY_PATTERN = re.compile(r"^CINE-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$")


def validate_key_format(key: str) -> bool:
    return bool(KEY_PATTERN.match(key.upper().strip()))


def validate_rating(rating: str) -> float | None:
    try:
        val = float(rating)
        if 1 <= val <= 10:
            return val
    except (ValueError, TypeError):
        pass
    return None


def validate_movie_title(title: str) -> str | None:
    if not title or not title.strip():
        return None
    cleaned = title.strip()
    if len(cleaned) > 200:
        return None
    return cleaned


def validate_key_type(key_type: str) -> bool:
    return key_type.upper() in KEY_TYPES


def validate_batch_name(name: str) -> str | None:
    if not name or not name.strip():
        return None
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]", "", name.strip())
    if len(cleaned) < 1 or len(cleaned) > 50:
        return None
    return cleaned


def validate_quantity(qty: str) -> int | None:
    try:
        val = int(qty)
        if 1 <= val <= 500:
            return val
    except (ValueError, TypeError):
        pass
    return None


def sanitize_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def parse_compare_query(text: str) -> tuple[str, str] | None:
    separators = [" vs ", " vs. ", " VS ", " versus ", " or "]
    for sep in separators:
        if sep in text:
            parts = text.split(sep, 1)
            a, b = parts[0].strip(), parts[1].strip()
            if a and b:
                return a, b
    return None