"""Inline keyboard for the /start command."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_start_keyboard() -> InlineKeyboardMarkup:
    """Start keyboard: a single big 'Book' button."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="💈 Записаться",
                callback_data="booking:start",
            ),
        ]]
    )