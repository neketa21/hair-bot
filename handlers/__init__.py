"""Collects all routers into a single root router."""
from __future__ import annotations

from aiogram import Router

from . import channels, errors, groups
from .users import booking, callbacks, echo, help, start


def setup_routers() -> Router:
    router = Router(name="main")
    router.include_routers(
    start.router,
    help.router,
    callbacks.router,
    booking.router,      # ← наш, до echo
    groups.router,
    channels.router,
    errors.router,
    echo.router,         # ← всегда последний
)
    return router
