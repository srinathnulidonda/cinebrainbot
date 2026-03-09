# bot/__init__.py
__version__ = "1.0.0"


class CineBotError(Exception):
    def __init__(self, message: str = "An error occurred", user_message: str | None = None):
        super().__init__(message)
        self.user_message = user_message or message


class MovieNotFoundError(CineBotError):
    def __init__(self, query: str = ""):
        super().__init__(f"Movie not found: {query}", f"🔍 No movies found for '{query}'. Try a different search term.")


class InvalidKeyError(CineBotError):
    def __init__(self):
        super().__init__("Invalid license key format", "❌ Invalid key format. Keys look like: <code>CINE-XXXX-XXXX-XXXX-XXXX</code>")


class KeyAlreadyUsedError(CineBotError):
    def __init__(self):
        super().__init__("Key already used", "❌ This key has already been redeemed.")


class KeyExpiredError(CineBotError):
    def __init__(self):
        super().__init__("Key expired", "❌ This key has expired.")


class KeyRevokedError(CineBotError):
    def __init__(self):
        super().__init__("Key revoked", "❌ This key has been revoked by an admin.")


class KeyNotFoundError(CineBotError):
    def __init__(self):
        super().__init__("Key not found", "❌ This key does not exist.")


class RateLimitExceededError(CineBotError):
    def __init__(self, feature: str = "this feature", reset_in: int = 0):
        mins = reset_in // 60 if reset_in else 0
        super().__init__(
            f"Rate limit exceeded for {feature}",
            f"⏳ You've hit the daily limit for {feature}. "
            f"{'Resets in ' + str(mins) + ' minutes.' if mins else 'Upgrade to Pro for unlimited access!'}"
        )


class SubscriptionRequiredError(CineBotError):
    def __init__(self, feature: str = "this feature"):
        super().__init__(f"Pro required for {feature}", f"🔒 <b>{feature}</b> is a Pro feature. Use /pro to learn about upgrading!")


class WatchlistFullError(CineBotError):
    def __init__(self, limit: int = 20):
        super().__init__("Watchlist full", f"📋 Your watchlist is full ({limit} items). Upgrade to Pro for unlimited or remove some movies.")


class DuplicateEntryError(CineBotError):
    def __init__(self, item: str = "item"):
        super().__init__(f"Duplicate {item}", f"ℹ️ This {item} already exists.")


class ExternalAPIError(CineBotError):
    def __init__(self, service: str = "external service"):
        super().__init__(f"{service} API error", f"⚠️ Could not reach {service}. Please try again shortly.")


class AdminRequiredError(CineBotError):
    def __init__(self):
        super().__init__("Admin access required", "🚫 This command is admin-only.")