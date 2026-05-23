"""Flash message utilities backed by Starlette session cookies."""

from starlette.requests import Request


_FLASH_KEY = "flash"
_VALID_CATEGORIES = ("success", "error", "warning", "info")


def set_flash(request: Request, message: str, category: str = "info") -> None:
    """Store a flash message in the session for display on the next request.

    Flash messages are consumed (removed) after being read once.
    Multiple calls accumulate messages in a list. The SessionMiddleware
    automatically serializes the session to a cookie at end of request.
    """
    if category not in _VALID_CATEGORIES:
        raise ValueError(
            f"Invalid flash category '{category}'. "
            f"Must be one of {_VALID_CATEGORIES}."
        )

    entry = (category, message)
    if _FLASH_KEY not in request.session or not isinstance(
        request.session[_FLASH_KEY], list
    ):
        request.session[_FLASH_KEY] = []
    request.session[_FLASH_KEY].append(entry)


def get_flashed_messages(request: Request) -> list[tuple[str, str]]:
    """Retrieve and consume flash messages from the current request's session.

    Returns a list of (category, message) tuples. Messages are removed from
    the session after being read, so calling this function again will return
    an empty list.
    """
    messages = request.session.get(_FLASH_KEY, [])
    if not isinstance(messages, list):
        messages = []

    # Clear the flash key so messages are consumed (one-time use)
    request.session.pop(_FLASH_KEY, None)

    return [(str(cat), str(msg)) for cat, msg in messages]
