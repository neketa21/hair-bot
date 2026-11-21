"""Inline keyboards for the barbershop booking flow."""
from __future__ import annotations

from datetime import date, timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# --- Domain data (edit here to change the barbershop) -----------------------

# key -> (display name, duration in minutes)
SERVICES: dict[str, tuple[str, int]] = {
    "cut": ("Мужская стрижка", 60),
    "cut_beard": ("Стрижка + борода", 90),
    "beard": ("Оформление бороды", 30),
    "gray": ("Камуфляж седины", 60),
}

MASTERS: dict[str, str] = {
    "ivan": "Иван",
    "sergey": "Сергей",
    "artem": "Артём",
}
# --- Keyboards --------------------------------------------------------------


def get_services_keyboard() -> InlineKeyboardMarkup:
    """Service picker: one button per service with its duration."""
    rows = [
        [InlineKeyboardButton(
            text=f"{name} · {duration} мин",
            callback_data=f"service:{key}",
        )]
        for key, (name, duration) in SERVICES.items()
    ]
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="booking:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_masters_keyboard() -> InlineKeyboardMarkup:
    """Master picker."""
    rows = [
        [InlineKeyboardButton(text=name, callback_data=f"master:{key}")]
        for key, name in MASTERS.items()
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="booking:back_service")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_days_keyboard() -> InlineKeyboardMarkup:
    """Next 7 days (today + 6). callback_data format: day:YYYY-MM-DD."""
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    today = date.today()
    rows: list[list[InlineKeyboardButton]] = []
    for offset in range(7):
        d = today + timedelta(days=offset)
        label = f"{weekdays[d.weekday()]} {d.strftime('%d.%m')}"
        rows.append([InlineKeyboardButton(
            text=label,
            callback_data=f"day:{d.isoformat()}",
        )])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="booking:back_master")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_slots_keyboard(free_slots: list[str]) -> InlineKeyboardMarkup:
    """3-column keyboard from a list of 'HH:MM' strings."""
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for slot in free_slots:
        row.append(InlineKeyboardButton(text=slot, callback_data=f"slot:{slot}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="booking:back_day")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    """Confirm / cancel the booking."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="booking:confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="booking:cancel"),
    ]])


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Single cancel button — used while waiting for the phone number."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отмена", callback_data="booking:cancel"),
    ]])