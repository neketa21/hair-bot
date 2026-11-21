"""FSM states for the barbershop booking flow."""
from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class Booking(StatesGroup):
    """Steps of the booking dialog.

    service  → user picks a service (Стрижка / Стрижка + борода / Камуфляж)
    master   → user picks a master (Александр / Дмитрий)
    day      → user picks a day (next 7 days)
    slot     → user picks a time slot (only free ones)
    phone    → user types a phone number
    confirm  → user confirms the booking
    """

    service = State()
    master = State()
    day = State()
    slot = State()
    phone = State()
    confirm = State()