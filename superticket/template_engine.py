"""Jinja2 template engine setup."""

import pathlib

from jinja2 import Environment, FileSystemLoader
from starlette.templating import Jinja2Templates

_TEMPLATES_DIR = pathlib.Path(__file__).parent / "templates"

# Use cache_size=0 to avoid hashing issues with SQLAlchemy model instances in context
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    cache_size=0,
)

# Add get_flashed_messages helper (no-op for now, can be wired to session/cookies later)
_jinja_env.globals["get_flashed_messages"] = lambda: []

templates = Jinja2Templates(env=_jinja_env)
