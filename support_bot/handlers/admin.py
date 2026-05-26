from datetime import datetime
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..config import Config, STATUS_EMOJI, STATUS_LABELS
from ..keyboards import MAIN_MENU, admin_panel_keyboard, admin_status_keyboard, admin_ticket_actions_keyboard, admin_ticket_list_keyboard, back_to_menu_keyboard
from ..services.ticket_service import TicketService
from ..states import AdminAnswer, AdminSearch


router = Router(name="admin")


@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext, config: Config) -> None:
    await state.clear()
    if not _is_admin(message.from_user.id if message.from_user else None, config):
        await message.answer("⛔ У вас нет доступа к админ-панели.")
        return

    await message.answer("Админ-панель:", reply_markup=admin_panel_keyboard())


@router.callback_query(F.data == "admin:panel")
async def admin_panel_callback(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not await _guard_admin_callback(callback, config):
        return

    await state.clear()
    await callback.answer()
    await callback.message.answer("Админ-панель:", reply_markup=admin_panel_keyboard())


@router.callback_query(F.data.startswith("admin:list:"))
async def admin_ticket_list(callback: CallbackQuery, ticket_service: TicketService, config: Config) -> None:
    if not await _guard_admin_callback(callback, config):
        return

    status = callback.data.rsplit(":", 1)[-1]
    if status not in STATUS_LABELS:
        await callback.answer("Неизвестный статус", show_alert=True)
        return

    tickets = await ticket_service.get_tickets_by_status(status)
    await callback.answer()
    if not tickets:
        await callback.message.answer(
            f"Обращений со статусом «{STATUS_LABELS[status]}» нет.",
            reply_markup=admin_ticket_list_keyboard([], status),
        )
        return

    await callback.message.answer(
        f"{STATUS_EMOJI.get(status, '')} Обращения: {STATUS_LABELS[status]}",
        reply_markup=admin_ticket_list_keyboard(tickets, status),
    )


@router.callback_query(F.data.startswith("admin:ticket:"))
async def admin_ticket_detail(callback: CallbackQuery, ticket_service: TicketService, config: Config) -> None:
    if not await _guard_admin_callback(callback, config):
        return

    ticket_id = int(callback.data.rsplit(":", 1)[-1])
    ticket = await ticket_service.get_ticket(ticket_id)
    await callback.answer()

    if ticket is None:
        await callback.message.answer("Обращение не найдено.", reply_markup=admin_panel_keyboard())
        return

    await callback.message.answer(
        format_admin_ticket(ticket),
        reply_markup=admin_ticket_actions_keyboard(ticket),
    )


@router.callback_query(F.data.startswith("admin:statuses:"))
async def admin_statuses(callback: CallbackQuery, ticket_service: TicketService, config: Config) -> None:
    if not await _guard_admin_callback(callback, config):
        return

    ticket_id = int(callback.data.rsplit(":", 1)[-1])
    ticket = await ticket_service.get_ticket(ticket_id)
    if ticket is None:
        await callback.answer("Обращение не найдено", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer(
        f"Выберите новый статус для обращения #{ticket_id}:",
        reply_markup=admin_status_keyboard(ticket_id),
    )


@router.callback_query(F.data.startswith("admin:set_status:"))
async def admin_set_status(
    callback: CallbackQuery,
    ticket_service: TicketService,
    config: Config,
    bot: Bot,
) -> None:
    if not await _guard_admin_callback(callback, config):
        return

    _, _, ticket_id_raw, status = callback.data.split(":", 3)
    ticket_id = int(ticket_id_raw)
    if status not in STATUS_LABELS:
        await callback.answer("Неизвестный статус", show_alert=True)
        return

    await ticket_service.update_status(ticket_id, status)
    ticket = await ticket_service.get_ticket(ticket_id)
    if ticket is None:
        await callback.answer("Обращение не найдено", show_alert=True)
        return

    await callback.answer("Статус изменен")
    await _notify_user_status(bot, ticket, status)
    await callback.message.answer(
        format_admin_ticket(ticket),
        reply_markup=admin_ticket_actions_keyboard(ticket),
    )


@router.callback_query(F.data.startswith("admin:answer:"))
async def admin_answer_start(
    callback: CallbackQuery,
    state: FSMContext,
    ticket_service: TicketService,
    config: Config,
) -> None:
    if not await _guard_admin_callback(callback, config):
        return

    ticket_id = int(callback.data.rsplit(":", 1)[-1])
    ticket = await ticket_service.get_ticket(ticket_id)
    if ticket is None:
        await callback.answer("Обращение не найдено", show_alert=True)
        return

    await state.update_data(ticket_id=ticket_id)
    await state.set_state(AdminAnswer.waiting_text)
    await callback.answer()
    await callback.message.answer(
        f"Напишите ответ пользователю по обращению #{ticket_id}.",
        reply_markup=back_to_menu_keyboard(),
    )


@router.message(StateFilter(AdminAnswer.waiting_text, AdminSearch.waiting_ticket_id), F.text == MAIN_MENU)
async def admin_cancel_state(message: Message, state: FSMContext, config: Config) -> None:
    await state.clear()
    if not _is_admin(message.from_user.id if message.from_user else None, config):
        await message.answer("Действие отменено.")
        return

    await message.answer("Действие отменено. Админ-панель открыта.", reply_markup=admin_panel_keyboard())


@router.message(StateFilter(AdminAnswer.waiting_text), F.text)
async def admin_answer_send(
    message: Message,
    state: FSMContext,
    ticket_service: TicketService,
    bot: Bot,
    config: Config,
) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None, config):
        await state.clear()
        await message.answer("⛔ У вас нет доступа.")
        return

    data = await state.get_data()
    ticket_id = int(data["ticket_id"])
    ticket = await ticket_service.get_ticket(ticket_id)
    if ticket is None:
        await state.clear()
        await message.answer("Обращение не найдено.", reply_markup=admin_panel_keyboard())
        return

    answer_text = message.text.strip()
    await ticket_service.add_message(ticket_id, "admin", message.from_user.id, answer_text)
    if str(ticket["status"]) == "new":
        await ticket_service.update_status(ticket_id, "in_progress")

    delivered = await _send_support_answer(bot, int(ticket["telegram_id"]), ticket_id, answer_text)
    await state.clear()

    updated_ticket = await ticket_service.get_ticket(ticket_id)
    delivery_text = "Сообщение отправлено пользователю." if delivered else "Ответ сохранен, но доставить сообщение пользователю не удалось."
    await message.answer(
        f"✅ {delivery_text}",
        reply_markup=admin_panel_keyboard(),
    )
    if updated_ticket is not None:
        await message.answer(format_admin_ticket(updated_ticket), reply_markup=admin_ticket_actions_keyboard(updated_ticket))


@router.message(StateFilter(AdminAnswer.waiting_text))
async def admin_answer_invalid(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте ответ текстом.")


@router.callback_query(F.data == "admin:find")
async def admin_find_start(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not await _guard_admin_callback(callback, config):
        return

    await state.set_state(AdminSearch.waiting_ticket_id)
    await callback.answer()
    await callback.message.answer("Введите номер обращения без #.", reply_markup=back_to_menu_keyboard())


@router.message(StateFilter(AdminSearch.waiting_ticket_id), F.text)
async def admin_find_result(
    message: Message,
    state: FSMContext,
    ticket_service: TicketService,
    config: Config,
) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None, config):
        await state.clear()
        await message.answer("⛔ У вас нет доступа.")
        return

    raw_ticket_id = message.text.strip().removeprefix("#")
    if not raw_ticket_id.isdigit():
        await message.answer("Введите числовой номер обращения, например 123.")
        return

    ticket_id = int(raw_ticket_id)
    ticket = await ticket_service.get_ticket(ticket_id)
    await state.clear()

    if ticket is None:
        await message.answer("Обращение не найдено.", reply_markup=admin_panel_keyboard())
        return

    await message.answer(format_admin_ticket(ticket), reply_markup=admin_ticket_actions_keyboard(ticket))


@router.message(StateFilter(AdminSearch.waiting_ticket_id))
async def admin_find_invalid(message: Message) -> None:
    await message.answer("Введите номер обращения текстом.")


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery, ticket_service: TicketService, config: Config) -> None:
    if not await _guard_admin_callback(callback, config):
        return

    stats = await ticket_service.get_stats()
    await callback.answer()
    await callback.message.answer(
        "📊 <b>Статистика обращений</b>\n\n"
        f"Всего: <b>{stats['total']}</b>\n"
        f"Новые: <b>{stats['new']}</b>\n"
        f"В работе: <b>{stats['in_progress']}</b>\n"
        f"Закрытые: <b>{stats['closed']}</b>",
        reply_markup=admin_panel_keyboard(),
    )


def format_admin_ticket(ticket) -> str:
    status = str(ticket["status"])
    username = f"@{ticket['username']}" if ticket["username"] else "без username"
    return (
        f"📌 <b>Обращение #{ticket['id']}</b>\n\n"
        f"<b>Пользователь:</b> {escape(str(ticket['first_name'] or ''))} ({escape(username)})\n"
        f"<b>Telegram ID:</b> <code>{ticket['telegram_id']}</code>\n"
        f"<b>Категория:</b> {escape(str(ticket['category']))}\n"
        f"<b>Статус:</b> {STATUS_EMOJI.get(status, '')} {STATUS_LABELS.get(status, status)}\n"
        f"<b>Создано:</b> {escape(_human_datetime(str(ticket['created_at'])))}\n\n"
        f"<b>Текст:</b>\n{escape(str(ticket['text']))}"
    )


async def _guard_admin_callback(callback: CallbackQuery, config: Config) -> bool:
    if not _is_admin(callback.from_user.id if callback.from_user else None, config):
        await callback.answer("Нет доступа", show_alert=True)
        return False
    return True


def _is_admin(user_id: int | None, config: Config) -> bool:
    return user_id is not None and user_id in config.admin_ids


async def _send_support_answer(bot: Bot, telegram_id: int, ticket_id: int, text: str) -> bool:
    try:
        await bot.send_message(
            telegram_id,
            f"💬 <b>Ответ поддержки по обращению #{ticket_id}:</b>\n\n{escape(text)}",
        )
        return True
    except TelegramAPIError:
        return False


async def _notify_user_status(bot: Bot, ticket, status: str) -> None:
    try:
        await bot.send_message(
            int(ticket["telegram_id"]),
            f"🔔 Статус обращения #{ticket['id']} изменен: {STATUS_EMOJI.get(status, '')} {STATUS_LABELS[status]}",
        )
    except TelegramAPIError:
        return


def _human_datetime(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return value
