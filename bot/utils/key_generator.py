# bot/utils/key_generator.py
import secrets
import string

_ALPHABET = string.ascii_uppercase + string.digits


def generate_key() -> str:
    groups = ["".join(secrets.choice(_ALPHABET) for _ in range(4)) for _ in range(4)]
    return f"CINE-{'-'.join(groups)}"


def generate_keys(count: int) -> list[str]:
    keys = set()
    while len(keys) < count:
        keys.add(generate_key())
    return list(keys)


def format_key_display(key: str) -> str:
    return f"<code>{key}</code>"


def format_keys_file(keys: list[str], key_type: str, batch_name: str) -> str:
    header = f"CineBot License Keys\nType: {key_type} | Batch: {batch_name}\nGenerated: {len(keys)} keys\n{'=' * 40}\n\n"
    body = "\n".join(keys)
    return header + body