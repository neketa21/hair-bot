"""Barbershop booking dialog.

Flow: /book (or callback 'booking:start') → service → master → day → slot
      → phone → confirm → create_booking() → notify admins.

Protection against double-booking is in database.create_booking(): it
re-checks the interval inside BEGIN IMMEDIATE and returns False if the
slot was taken between showing the keyboard and pressing "Confirm".
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from data.config import settings
from database import create_booking, get_free_slots
from keyboards.inline import (
    MASTERS,
    SERVICES,
    get_cancel_keyboard,
    get_confirm_keyboard,
    get_days_keyboard,
    get_masters_keyboard,
    get_services_keyboard,
    get_slots_keyboard,
)
from states.booking import Booking

router = Router(name="users:booking")


# --- Step 0: entry point ----------------------------------------------------


@router.message(Command("book"))
async def cmd_book(message: Message, state: FSMContext) -> None:
    """Start the booking dialog from scratch."""
    await state.clear()
    await state.set_state(Booking.service)
    await message.answer(
        "💈 <b>Запись в барбершоп</b>\n\nВыберите услугу:",
        reply_markup=get_services_keyboard(),
    )


@router.callback_query(F.data == "booking:start")
async def cb_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Same as /book, but triggered from an inline button."""
    await state.clear()
    await state.set_state(Booking.service)
    await callback.message.edit_text(
        "💈 <b>Запись в барбершоп</b>\n\nВыберите услугу:",
        reply_markup=get_services_keyboard(),
    )
    await callback.answer()


# --- Step 1: service --------------------------------------------------------


@router.callback_query(Booking.service, F.data.startswith("service:"))
async def cb_service(callback: CallbackQuery, state: FSMContext) -> None:
    key = callback.data.split(":", 1)[1]
    if key not in SERVICES:
        await callback.answer("Неизвестная услуга", show_alert=True)
        return
    name, duration = SERVICES[key]
    await state.update_data(service_key=key, service_name=name, duration=duration)
    await state.set_state(Booking.master)
    await callback.message.edit_text(
        f"Услуга: <b>{name}</b> ({duration} мин)\n\nВыберите мастера:",
        reply_markup=get_masters_keyboard(),
    )
    await callback.answer()


# --- Step 2: master ---------------------------------------------------------


@router.callback_query(Booking.master, F.data.startswith("master:"))
async def cb_master(callback: CallbackQuery, state: FSMContext) -> None:
    key = callback.data.split(":", 1)[1]
    if key not in MASTERS:
        await callback.answer("Неизвестный мастер", show_alert=True)
        return
    name = MASTERS[key]
    await state.update_data(master_key=key, master_name=name)
    await state.set_state(Booking.day)
    data = await state.get_data()
    await callback.message.edit_text(
        f"Услуга: <b>{data['service_name']}</b>\n"
        f"Мастер: <b>{name}</b>\n\nВыберите день:",
        reply_markup=get_days_keyboard(),
    )
    await callback.answer()


# --- Step 3: day ------------------------------------------------------------


@router.callback_query(Booking.day, F.data.startswith("day:"))
async def cb_day(callback: CallbackQuery, state: FSMContext) -> None:
    day = callback.data.split(":", 1)[1]
    data = await state.get_data()
    free = await get_free_slots(data["master_key"], day, data["duration"])
    if not free:
        await callback.answer("На этот день нет свободных слотов", show_alert=True)
        return
    await state.update_data(day=day)
    await state.set_state(Booking.slot)
    await callback.message.edit_text(
        f"Услуга: <b>{data['service_name']}</b>\n"
        f"Мастер: <b>{data['master_name']}</b>\n"
        f"День: <b>{day}</b>\n\nВыберите время:",
        reply_markup=get_slots_keyboard(free),
    )
    await callback.answer()


# --- Step 4: slot -----------------------------------------------------------


@router.callback_query(Booking.slot, F.data.startswith("slot:"))
async def cb_slot(callback: CallbackQuery, state: FSMContext) -> None:
    slot = callback.data.split(":", 1)[1]
    await state.update_data(slot=slot)
    await state.set_state(Booking.phone)
    data = await state.get_data()
    await callback.message.edit_text(
        f"Услуга: <b>{data['service_name']}</b>\n"
        f"Мастер: <b>{data['master_name']}</b>\n"
        f"Когда: <b>{data['day']} в {slot}</b>\n\n"
        "Оставьте номер телефона для подтверждения:",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


# --- Step 5: phone ----------------------------------------------------------


@router.message(Booking.phone, F.text)
async def msg_phone(message: Message, state: FSMContext) -> None:
    phone = (message.text or "").strip()
    if len(phone) < 5 or not any(ch.isdigit() for ch in phone):
        await message.answer(
            "Похоже, это не номер. Введите телефон (например, +7 999 123-45-67):"
        )
        return
    await state.update_data(phone=phone)
    await state.set_state(Booking.confirm)
    data = await state.get_data()
    await message.answer(
        "Проверьте запись:\n\n"
        f"Услуга: <b>{data['service_name']}</b> ({data['duration']} мин)\n"
        f"Мастер: <b>{data['master_name']}</b>\n"
        f"Когда: <b>{data['day']} в {data['slot']}</b>\n"
        f"Телефон: <b>{phone}</b>\n\n"
        "Всё верно?",
        reply_markup=get_confirm_keyboard(),
    )


# --- Step 6: confirm --------------------------------------------------------


@router.callback_query(Booking.confirm, F.data == "booking:confirm")
async def cb_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    user = callback.from_user
    ok = await create_booking(
        client_id=user.id,
        client_name=user.full_name,
        client_phone=data["phone"],
        master=data["master_key"],
        service=data["service_key"],
        day=data["day"],
        start_hhmm=data["slot"],
        duration_min=data["duration"],
    )
    if not ok:
        free = await get_free_slots(data["master_key"], data["day"], data["duration"])
        if not free:
            await state.clear()
            await callback.message.edit_text(
                "😔 Увы, этот слот только что заняли, "
                "и на этот день больше нет свободных."
            )
        else:
            await state.set_state(Booking.slot)
            await callback.message.edit_text(
                "😔 Этот слот только что заняли. Выберите другое время:",
                reply_markup=get_slots_keyboard(free),
            )
        await callback.answer()
        return

    await state.clear()
    await callback.message.edit_text(
        "✅ <b>Вы записаны!</b>\n\n"
        f"Услуга: <b>{data['service_name']}</b>\n"
        f"Мастер: <b>{data['master_name']}</b>\n"
        f"Когда: <b>{data['day']} в {data['slot']}</b>\n"
        f"Телефон: <b>{data['phone']}</b>\n\n"
        "Ждём вас!"
    )

    admin_text = (
        "🆕 <b>Новая запись</b>\n\n"
        f"Клиент: {user.full_name} (@{user.username or '—'}, id={user.id})\n"
        f"Телефон: {data['phone']}\n"
        f"Услуга: {data['service_name']}\n"
        f"Мастер: {data['master_name']}\n"
        f"Когда: {data['day']} в {data['slot']}"
    )
    for admin_id in settings.admins:
        try:
            await callback.bot.send_message(admin_id, admin_text)
        except Exception:
            pass
    await callback.answer("Готово!")


# --- Cancel / back ----------------------------------------------------------


@router.callback_query(F.data == "booking:cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Запись отменена. Если захотите — /book")
    await callback.answer()


@router.callback_query(F.data == "booking:back_service")
async def cb_back_service(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Booking.service)
    await callback.message.edit_text(
        "💈 <b>Запись в барбершоп</b>\n\nВыберите услугу:",
        reply_markup=get_services_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "booking:back_master")
async def cb_back_master(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(Booking.master)
    await callback.message.edit_text(
        f"Услуга: <b>{data['service_name']}</b> ({data['duration']} мин)\n\n"
        "Выберите мастера:",
        reply_markup=get_masters_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "booking:back_day")
async def cb_back_day(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(Booking.day)
    await callback.message.edit_text(
        f"Услуга: <b>{data['service_name']}</b>\n"
        f"Мастер: <b>{data['master_name']}</b>\n\nВыберите день:",
        reply_markup=get_days_keyboard(),
    )
    await callback.answer()