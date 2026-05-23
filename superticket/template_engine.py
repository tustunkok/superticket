"""Jinja2 template engine setup with flash message support."""

from typing import Any

import pathlib
from jinja2 import Environment, FileSystemLoader
from starlette.requests import Request
from starlette.templating import Jinja2Templates

from superticket.core.flash import get_flashed_messages

_TEMPLATES_DIR = pathlib.Path(__file__).parent / "templates"

_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    cache_size=0,
)


class FlashTemplates(Jinja2Templates):
    """Jinja2Templates subclass that auto-injects flash messages into context."""

    def get_context(
        self, context: dict[str, Any], request: Request
    ) -> dict[str, Any]:
        ctx = super().get_context(context, request)
        ctx["flash_messages"] = get_flashed_messages(request)
        return ctx


templates = FlashTemplates(env=_jinja_env)
