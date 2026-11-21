"""Handles the /start command."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from keyboards.inline import get_start_keyboard

router = Router(name="users:start")


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    name = message.from_user.first_name if message.from_user else "друг"
    await message.answer(
        f"💈 <b>Барбершоп «Manstyle»</b>\n\n"
        f"Привет, <b>{name}</b>!\n\n"
        "Здесь можно записаться к мастеру за пару кликов:\n"
        "• выбрать услугу\n"
        "• выбрать мастера\n"
        "• выбрать удобный день и время\n\n"
        "Нажмите кнопку ниже, чтобы начать запись 👇",
        reply_markup=get_start_keyboard(),
    )