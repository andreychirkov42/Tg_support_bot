import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from ..config import Config, STATUS_LABELS, TICKET_STATUSES
from ..keyboards import admin_message_keyboard, admin_panel_keyboard, admin_ticket_keyboard, admin_ticket_list_keyboard
from ..services.admin_service import AdminService
from ..services.ticket_service import TicketService
from ..services.user_service import UserService
from ..utils.formatting import format_admin_ticket, format_stats, format_ticket_history, html, status_text
from ..utils.permissions import is_admin_callback, is_admin_chat_id, is_admin_id, is_admin_message


router = Router(name="admin_channel")
logger = logging.getLogger(__name__)


async def publish_ticket_card(bot: Bot, config: Config, ticket_service: TicketService, ticket_id: int) -> bool:
    if config.admin_chat_id is None:
        logger.warning("ADMIN_CHAT_ID is empty; ticket %s was not published", ticket_id)
        return False

    ticket = await ticket_service.get_ticket(ticket_id)
    if ticket is None:
        return False

    try:
        sent = await bot.send_message(
            config.admin_chat_id,
            format_admin_ticket(ticket, title=f"🆕 <b>Новое обращение #{ticket_id}</b>"),
            reply_markup=admin_ticket_keyboard(ticket),
        )
    except TelegramAPIError as exc:
        logger.warning("Failed to publish ticket %s to admin chat: %s", ticket_id, exc)
        return False

    await ticket_service.set_admin_message_id(ticket_id, sent.message_id)
    await ticket_service.create_reply_link(ticket_id, sent.message_id)
    return True


@router.message(Command("admin"))
async def admin_command(message: Message, config: Config) -> None:
    if not is_admin_chat_id(message.chat.id, config):
        await message.answer("Админ-панель доступна только в рабочем канале поддержки.")
        return
    if message.from_user is not None and not is_admin_id(message.from_user.id, config):
        await message.answer("⛔ У вас нет доступа к панели поддержки.")
        return

    await message.answer("🛠 <b>Панель поддержки</b>", reply_markup=admin_panel_keyboard())


@router.channel_post(Command("admin"))
async def admin_channel_command(message: Message, config: Config) -> None:
    if is_admin_chat_id(message.chat.id, config):
        await message.answer("🛠 <b>Панель поддержки</b>", reply_markup=admin_panel_keyboard())


@router.callback_query(F.data.startswith("a:"))
async def admin_callback(
    callback: CallbackQuery,
    bot: Bot,
    config: Config,
    ticket_service: TicketService,
    user_service: UserService,
    admin_service: AdminService,
) -> None:
    if not is_admin_callback(callback, config):
        await callback.answer("Нет доступа", show_alert=True)
        return

    parts = (callback.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""

    try:
        if action == "panel":
            await callback.answer()
            await callback.message.answer("🛠 <b>Панель поддержки</b>", reply_markup=admin_panel_keyboard())
        elif action == "list" and len(parts) == 3:
            await _show_ticket_list(callback, ticket_service, parts[2])
        elif action == "stats":
            await _show_stats(callback, ticket_service)
        elif action == "find":
            await _start_find(callback, ticket_service)
        elif action == "open" and len(parts) == 3:
            await _show_history(callback, ticket_service, int(parts[2]))
        elif action == "answer" and len(parts) == 3:
            await _answer_prompt(callback, ticket_service, int(parts[2]))
        elif action == "work" and len(parts) == 3:
            await _set_status(callback, bot, config, ticket_service, admin_service, int(parts[2]), "in_progress")
        elif action == "close" and len(parts) == 3:
            await _set_status(callback, bot, config, ticket_service, admin_service, int(parts[2]), "closed")
        elif action in {"block", "unblock"} and len(parts) == 4:
            await _set_blocked(
                callback,
                bot,
                config,
                ticket_service,
                user_service,
                admin_service,
                telegram_id=int(parts[2]),
                ticket_id=int(parts[3]),
                blocked=action == "block",
            )
        else:
            await callback.answer("Действие устарело или некорректно", show_alert=True)
    except (ValueError, KeyError):
        await callback.answer("Некорректные данные кнопки", show_alert=True)


@router.message(F.reply_to_message)
async def admin_reply_message(
    message: Message,
    bot: Bot,
    config: Config,
    ticket_service: TicketService,
    admin_service: AdminService,
) -> None:
    await _handle_admin_reply(message, bot, config, ticket_service, admin_service)


@router.channel_post(F.reply_to_message)
async def admin_reply_channel_post(
    message: Message,
    bot: Bot,
    config: Config,
    ticket_service: TicketService,
    admin_service: AdminService,
) -> None:
    await _handle_admin_reply(message, bot, config, ticket_service, admin_service)


async def _handle_admin_reply(
    message: Message,
    bot: Bot,
    config: Config,
    ticket_service: TicketService,
    admin_service: AdminService,
) -> None:
    if not is_admin_chat_id(message.chat.id, config):
        return
    if message.from_user is not None and not is_admin_message(message, config):
        await message.answer("⛔ У вас нет доступа к обращениям.")
        return
    if message.text and message.text.startswith("/"):
        return

    reply_to = message.reply_to_message
    if reply_to is None:
        return

    ticket_id = await ticket_service.resolve_reply_link(reply_to.message_id)
    if ticket_id is None:
        return

    if ticket_id == 0:
        await _handle_find_reply(message, ticket_service)
        return

    text = (message.text or message.caption or "").strip()
    if not text:
        await message.answer("Пока можно отправлять пользователю только текстовый ответ.")
        return

    ticket = await ticket_service.get_ticket(ticket_id)
    if ticket is None:
        await message.answer("Обращение не найдено.")
        return

    admin_id = message.from_user.id if message.from_user else 0
    await ticket_service.add_message(ticket_id, "admin", admin_id, text, admin_message_id=message.message_id)
    await ticket_service.create_reply_link(ticket_id, message.message_id)
    await admin_service.log_action(admin_id, ticket_id, "reply")

    if str(ticket["status"]) == "new":
        await ticket_service.update_status(ticket_id, "in_progress")
        await _update_original_card(bot, config, ticket_service, ticket_id)

    delivered = await _send_support_answer(bot, int(ticket["telegram_id"]), ticket_id, text)
    if delivered:
        await message.answer(f"✅ Ответ по обращению #{ticket_id} отправлен пользователю.")
    else:
        await message.answer(f"⚠️ Ответ по обращению #{ticket_id} сохранен, но отправить его пользователю не удалось.")


async def _show_ticket_list(callback: CallbackQuery, ticket_service: TicketService, status: str) -> None:
    if status not in TICKET_STATUSES:
        await callback.answer("Неизвестный статус", show_alert=True)
        return

    tickets = await ticket_service.get_tickets_by_status(status)
    await callback.answer()
    if not tickets:
        await callback.message.answer(f"{status_text(status)}\n\nОбращений пока нет.", reply_markup=admin_panel_keyboard())
        return

    await callback.message.answer(
        f"{status_text(status)}\n\nВыберите обращение:",
        reply_markup=admin_ticket_list_keyboard(tickets),
    )


async def _show_stats(callback: CallbackQuery, ticket_service: TicketService) -> None:
    stats = await ticket_service.get_stats()
    await callback.answer()
    await callback.message.answer(format_stats(stats), reply_markup=admin_panel_keyboard())


async def _start_find(callback: CallbackQuery, ticket_service: TicketService) -> None:
    await callback.answer()
    sent = await callback.message.answer("🔍 Ответьте на это сообщение номером обращения.")
    await ticket_service.create_reply_link(0, sent.message_id)


async def _handle_find_reply(message: Message, ticket_service: TicketService) -> None:
    raw_ticket_id = (message.text or "").strip().removeprefix("#")
    if not raw_ticket_id.isdigit():
        await message.answer("Введите номер обращения числом, например 123.")
        return

    ticket = await ticket_service.get_ticket(int(raw_ticket_id))
    if ticket is None:
        await message.answer("Обращение не найдено.", reply_markup=admin_panel_keyboard())
        return

    sent = await message.answer(format_admin_ticket(ticket), reply_markup=admin_ticket_keyboard(ticket))
    await ticket_service.create_reply_link(int(ticket["id"]), sent.message_id)


async def _show_history(callback: CallbackQuery, ticket_service: TicketService, ticket_id: int) -> None:
    ticket = await ticket_service.get_ticket(ticket_id)
    if ticket is None:
        await callback.answer("Обращение не найдено", show_alert=True)
        return

    messages = await ticket_service.get_ticket_messages(ticket_id)
    await callback.answer()
    sent = await callback.message.answer(
        format_ticket_history(ticket, messages),
        reply_markup=admin_ticket_keyboard(ticket),
    )
    await ticket_service.create_reply_link(ticket_id, sent.message_id)


async def _answer_prompt(callback: CallbackQuery, ticket_service: TicketService, ticket_id: int) -> None:
    ticket = await ticket_service.get_ticket(ticket_id)
    if ticket is None:
        await callback.answer("Обращение не найдено", show_alert=True)
        return

    await callback.answer()
    sent = await callback.message.answer(
        f"💬 Напишите ответ на это сообщение reply-сообщением, чтобы отправить его пользователю по обращению #{ticket_id}."
    )
    await ticket_service.create_reply_link(ticket_id, sent.message_id)


async def _set_status(
    callback: CallbackQuery,
    bot: Bot,
    config: Config,
    ticket_service: TicketService,
    admin_service: AdminService,
    ticket_id: int,
    status: str,
) -> None:
    ticket = await ticket_service.get_ticket(ticket_id)
    if ticket is None:
        await callback.answer("Обращение не найдено", show_alert=True)
        return

    await ticket_service.update_status(ticket_id, status)
    await admin_service.log_action(callback.from_user.id, ticket_id, f"status:{status}")
    await _update_original_card(bot, config, ticket_service, ticket_id)

    updated = await ticket_service.get_ticket(ticket_id)
    await callback.answer("Статус обновлен")
    if updated is not None:
        await callback.message.answer(format_admin_ticket(updated), reply_markup=admin_ticket_keyboard(updated))

    if status == "in_progress":
        await _safe_send_user(bot, int(ticket["telegram_id"]), f"🟡 Ваше обращение #{ticket_id} взято в работу.")
    elif status == "closed":
        await _safe_send_user(bot, int(ticket["telegram_id"]), f"✅ Ваше обращение #{ticket_id} закрыто. Спасибо за обращение!")


async def _set_blocked(
    callback: CallbackQuery,
    bot: Bot,
    config: Config,
    ticket_service: TicketService,
    user_service: UserService,
    admin_service: AdminService,
    *,
    telegram_id: int,
    ticket_id: int,
    blocked: bool,
) -> None:
    ticket = await ticket_service.get_ticket(ticket_id)
    if ticket is None:
        await callback.answer("Обращение не найдено", show_alert=True)
        return

    await user_service.set_blocked(telegram_id, blocked)
    await admin_service.log_action(callback.from_user.id, ticket_id, "block" if blocked else "unblock")
    await _update_original_card(bot, config, ticket_service, ticket_id)

    await callback.answer("Готово")
    updated = await ticket_service.get_ticket(ticket_id)
    if updated is not None:
        action_text = "заблокирован" if blocked else "разблокирован"
        await callback.message.answer(
            f"✅ Пользователь {action_text}.\n\n" + format_admin_ticket(updated),
            reply_markup=admin_ticket_keyboard(updated),
        )

    if blocked:
        await _safe_send_user(bot, telegram_id, "🚫 Доступ к поддержке ограничен.")


async def _update_original_card(bot: Bot, config: Config, ticket_service: TicketService, ticket_id: int) -> None:
    ticket = await ticket_service.get_ticket(ticket_id)
    if ticket is None or config.admin_chat_id is None or ticket["admin_chat_message_id"] is None:
        return

    try:
        await bot.edit_message_text(
            chat_id=config.admin_chat_id,
            message_id=int(ticket["admin_chat_message_id"]),
            text=format_admin_ticket(ticket),
            reply_markup=admin_ticket_keyboard(ticket),
        )
    except TelegramAPIError as exc:
        logger.info("Could not edit original ticket card %s: %s", ticket_id, exc)


async def _send_support_answer(bot: Bot, telegram_id: int, ticket_id: int, text: str) -> bool:
    return await _safe_send_user(
        bot,
        telegram_id,
        f"💬 <b>Ответ поддержки по обращению #{ticket_id}:</b>\n\n{html(text)}",
    )


async def _safe_send_user(bot: Bot, telegram_id: int, text: str) -> bool:
    try:
        await bot.send_message(telegram_id, text)
        return True
    except TelegramAPIError as exc:
        logger.warning("Failed to send message to user %s: %s", telegram_id, exc)
        return False
