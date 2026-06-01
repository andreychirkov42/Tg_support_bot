import logging
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User

from ..config import Config
from ..keyboards import (
    BACK,
    CATEGORIES,
    CREATE_TICKET,
    FEEDBACK,
    MAIN_MENU,
    MY_TICKETS,
    admin_message_keyboard,
    back_menu_keyboard,
    categories_keyboard,
    main_menu_keyboard,
    ticket_preview_keyboard,
    user_ticket_detail_keyboard,
    user_tickets_keyboard,
)
from ..services.feedback_service import FeedbackService
from ..services.ticket_service import TicketService
from ..services.user_service import UserService
from ..states import AddTicketMessage, CreateTicket, SendFeedback
from ..utils.formatting import (
    format_feedback_notice,
    format_ticket_preview,
    format_user_message_notice,
    format_user_ticket,
    html,
)
from .admin_channel import publish_ticket_card


router = Router(name="user")
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, user_service: UserService) -> None:
    await state.clear()
    if message.from_user is not None:
        await user_service.ensure_user(message.from_user)

    await message.answer(
        "👋 <b>Здравствуйте!</b>\n\n"
        "Я бот службы поддержки. Помогу создать обращение и посмотреть его статус.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text.in_({MAIN_MENU, BACK}))
async def main_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("🏠 Главное меню. Чем помочь?", reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "u:menu")
async def main_menu_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.answer("🏠 Главное меню. Чем помочь?", reply_markup=main_menu_keyboard())


@router.message(F.text == CREATE_TICKET)
async def create_ticket_start(message: Message, state: FSMContext, user_service: UserService, config: Config) -> None:
    if not await _can_create_ticket(message, user_service, config):
        return

    await state.set_state(CreateTicket.choosing_category)
    await message.answer("📂 Выберите категорию обращения:", reply_markup=categories_keyboard())


@router.callback_query(StateFilter(CreateTicket.choosing_category), F.data.startswith("u:cat:"))
async def choose_category(callback: CallbackQuery, state: FSMContext) -> None:
    category_code = callback.data.rsplit(":", 1)[-1]
    category = CATEGORIES.get(category_code)
    if category is None:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    await state.update_data(category=category, created_at=datetime.now().strftime("%d.%m.%Y %H:%M"))
    await state.set_state(CreateTicket.waiting_text)
    await callback.answer()
    await callback.message.answer(
        f"📂 <b>{html(category)}</b>\n\nОпишите проблему одним сообщением. Чем больше деталей, тем быстрее поможем.",
        reply_markup=back_menu_keyboard(),
    )


@router.message(StateFilter(CreateTicket.waiting_text), F.text)
async def receive_ticket_text(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if len(text) < 5:
        await message.answer("Добавьте немного деталей: что случилось и что вы уже пробовали?")
        return

    await state.update_data(text=text)
    data = await state.get_data()
    await state.set_state(CreateTicket.preview)
    await message.answer(
        format_ticket_preview(str(data["category"]), text, str(data["created_at"])),
        reply_markup=ticket_preview_keyboard(),
    )


@router.message(StateFilter(CreateTicket.waiting_text))
async def receive_ticket_text_invalid(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте описание проблемы текстом.")


@router.callback_query(StateFilter(CreateTicket.preview), F.data == "u:ticket:edit")
async def edit_ticket_text(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CreateTicket.waiting_text)
    await callback.answer()
    await callback.message.answer("✏️ Отправьте новый текст обращения.", reply_markup=back_menu_keyboard())


@router.callback_query(StateFilter(CreateTicket.preview), F.data == "u:ticket:cancel")
async def cancel_ticket(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Отменено")
    await callback.message.answer("❌ Обращение отменено.", reply_markup=main_menu_keyboard())


@router.callback_query(StateFilter(CreateTicket.preview), F.data == "u:ticket:send")
async def send_ticket(
    callback: CallbackQuery,
    state: FSMContext,
    ticket_service: TicketService,
    user_service: UserService,
    bot: Bot,
    config: Config,
) -> None:
    if callback.from_user is None:
        await callback.answer("Не удалось определить пользователя", show_alert=True)
        return
    if await user_service.is_blocked(callback.from_user.id):
        await state.clear()
        await callback.answer("Доступ ограничен", show_alert=True)
        await callback.message.answer("🚫 Доступ к поддержке ограничен.", reply_markup=main_menu_keyboard())
        return

    data = await state.get_data()
    ticket_id = await ticket_service.create_ticket(callback.from_user, str(data["category"]), str(data["text"]))
    await state.clear()

    published = await publish_ticket_card(bot, config, ticket_service, ticket_id)
    await callback.answer("Обращение создано")
    if published:
        await callback.message.answer(
            f"✅ Обращение #{ticket_id} создано. Поддержка скоро ответит вам.",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await callback.message.answer(
            f"✅ Обращение #{ticket_id} создано, но сейчас не удалось уведомить поддержку. Мы сохранили заявку и попробуем обработать ее позже.",
            reply_markup=main_menu_keyboard(),
        )


@router.message(F.text == MY_TICKETS)
async def my_tickets(message: Message, ticket_service: TicketService) -> None:
    if message.from_user is None:
        return
    await _send_user_tickets(message, ticket_service, message.from_user.id)


@router.callback_query(F.data == "u:tickets")
async def my_tickets_callback(callback: CallbackQuery, ticket_service: TicketService) -> None:
    await callback.answer()
    await _send_user_tickets(callback.message, ticket_service, callback.from_user.id)


@router.callback_query(F.data.startswith("u:t:"))
async def ticket_detail(callback: CallbackQuery, ticket_service: TicketService) -> None:
    ticket_id = _callback_int_tail(callback.data)
    if ticket_id is None:
        await callback.answer("Некорректное действие", show_alert=True)
        return

    ticket = await ticket_service.get_ticket_for_user(ticket_id, callback.from_user.id)
    await callback.answer()
    if ticket is None:
        await callback.message.answer("Обращение не найдено.", reply_markup=main_menu_keyboard())
        return

    await callback.message.answer(
        format_user_ticket(ticket),
        reply_markup=user_ticket_detail_keyboard(ticket_id, str(ticket["status"])),
    )


@router.callback_query(F.data.startswith("u:refresh:"))
async def refresh_ticket(callback: CallbackQuery, ticket_service: TicketService) -> None:
    ticket_id = _callback_int_tail(callback.data)
    if ticket_id is None:
        await callback.answer("Некорректное действие", show_alert=True)
        return

    ticket = await ticket_service.get_ticket_for_user(ticket_id, callback.from_user.id)
    if ticket is None:
        await callback.answer("Обращение не найдено", show_alert=True)
        return

    await callback.answer("Статус обновлен")
    await callback.message.answer(
        format_user_ticket(ticket),
        reply_markup=user_ticket_detail_keyboard(ticket_id, str(ticket["status"])),
    )


@router.callback_query(F.data.startswith("u:add:"))
async def add_message_start(callback: CallbackQuery, state: FSMContext, ticket_service: TicketService, user_service: UserService) -> None:
    ticket_id = _callback_int_tail(callback.data)
    if ticket_id is None:
        await callback.answer("Некорректное действие", show_alert=True)
        return
    if await user_service.is_blocked(callback.from_user.id):
        await callback.answer("Доступ ограничен", show_alert=True)
        await callback.message.answer("🚫 Доступ к поддержке ограничен.", reply_markup=main_menu_keyboard())
        return

    ticket = await ticket_service.get_ticket_for_user(ticket_id, callback.from_user.id)
    if ticket is None:
        await callback.answer("Обращение не найдено", show_alert=True)
        return
    if str(ticket["status"]) == "closed":
        await callback.answer("Обращение закрыто", show_alert=True)
        await callback.message.answer("Это обращение закрыто. Создайте новое, если вопрос остался.", reply_markup=main_menu_keyboard())
        return

    await state.update_data(ticket_id=ticket_id)
    await state.set_state(AddTicketMessage.waiting_text)
    await callback.answer()
    await callback.message.answer("💬 Напишите дополнительное сообщение по обращению.", reply_markup=back_menu_keyboard())


@router.message(StateFilter(AddTicketMessage.waiting_text), F.text)
async def add_message_send(
    message: Message,
    state: FSMContext,
    ticket_service: TicketService,
    user_service: UserService,
    bot: Bot,
    config: Config,
) -> None:
    if message.from_user is None:
        return
    if await user_service.is_blocked(message.from_user.id):
        await state.clear()
        await message.answer("🚫 Доступ к поддержке ограничен.", reply_markup=main_menu_keyboard())
        return

    data = await state.get_data()
    ticket_id = int(data["ticket_id"])
    ticket = await ticket_service.get_ticket(ticket_id)
    if ticket is None or int(ticket["telegram_id"]) != message.from_user.id:
        await state.clear()
        await message.answer("Обращение не найдено.", reply_markup=main_menu_keyboard())
        return
    if str(ticket["status"]) == "closed":
        await state.clear()
        await message.answer("Это обращение уже закрыто. Создайте новое обращение.", reply_markup=main_menu_keyboard())
        return

    text = message.text.strip()
    if len(text) < 2:
        await message.answer("Сообщение слишком короткое. Напишите чуть подробнее.")
        return

    message_id = await ticket_service.add_message(ticket_id, "user", message.from_user.id, text)
    await state.clear()
    await message.answer("✅ Сообщение добавлено к обращению.", reply_markup=main_menu_keyboard())
    await _notify_admin_about_user_message(bot, config, ticket_service, ticket_id, message_id, text)


@router.message(StateFilter(AddTicketMessage.waiting_text))
async def add_message_invalid(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте сообщение текстом.")


@router.message(F.text == FEEDBACK)
async def feedback_start(message: Message, state: FSMContext, user_service: UserService) -> None:
    if message.from_user is None:
        await message.answer("Не удалось определить пользователя. Откройте бота через /start.")
        return
    await user_service.ensure_user(message.from_user)
    if await user_service.is_blocked(message.from_user.id):
        await message.answer("🚫 Доступ к поддержке ограничен.", reply_markup=main_menu_keyboard())
        return

    await state.set_state(SendFeedback.waiting_text)
    await message.answer(
        "💡 Поделитесь отзывом или предложением одним сообщением. "
        "Это не создаёт обращение — мы просто прочитаем ваш фидбек.",
        reply_markup=back_menu_keyboard(),
    )


@router.message(StateFilter(SendFeedback.waiting_text), F.text)
async def feedback_send(
    message: Message,
    state: FSMContext,
    feedback_service: FeedbackService,
    user_service: UserService,
    bot: Bot,
    config: Config,
) -> None:
    if message.from_user is None:
        return
    if await user_service.is_blocked(message.from_user.id):
        await state.clear()
        await message.answer("🚫 Доступ к поддержке ограничен.", reply_markup=main_menu_keyboard())
        return

    text = message.text.strip()
    if len(text) < 5:
        await message.answer("Напишите чуть подробнее — так отзыв будет полезнее.")
        return

    await feedback_service.create_feedback(message.from_user, text)
    await state.clear()
    await message.answer("🙏 Спасибо за отзыв! Мы обязательно его учтём.", reply_markup=main_menu_keyboard())
    await _notify_admin_about_feedback(bot, config, message.from_user, text)


@router.message(StateFilter(SendFeedback.waiting_text))
async def feedback_invalid(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте отзыв текстом.")


async def _can_create_ticket(message: Message, user_service: UserService, config: Config) -> bool:
    if message.from_user is None:
        await message.answer("Не удалось определить пользователя. Откройте бота через /start.")
        return False
    await user_service.ensure_user(message.from_user)
    if await user_service.is_blocked(message.from_user.id):
        await message.answer("🚫 Доступ к поддержке ограничен.", reply_markup=main_menu_keyboard())
        return False
    if config.admin_chat_id is None:
        await message.answer("⚠️ Поддержка временно не настроена. Попробуйте позже.", reply_markup=main_menu_keyboard())
        return False
    return True


async def _send_user_tickets(message: Message, ticket_service: TicketService, telegram_id: int) -> None:
    tickets = await ticket_service.get_user_tickets(telegram_id)
    if not tickets:
        await message.answer("У вас пока нет обращений. Создайте первое через главное меню.", reply_markup=main_menu_keyboard())
        return
    await message.answer("📋 <b>Ваши обращения</b>", reply_markup=user_tickets_keyboard(tickets))


async def _notify_admin_about_user_message(
    bot: Bot,
    config: Config,
    ticket_service: TicketService,
    ticket_id: int,
    user_message_db_id: int,
    text: str,
) -> None:
    if config.admin_chat_id is None:
        return
    ticket = await ticket_service.get_ticket(ticket_id)
    if ticket is None:
        return

    try:
        sent = await bot.send_message(
            config.admin_chat_id,
            format_user_message_notice(ticket, text),
            reply_markup=admin_message_keyboard(ticket_id),
        )
    except TelegramAPIError as exc:
        logger.warning("Failed to notify admin chat about ticket %s message: %s", ticket_id, exc)
        return

    await ticket_service.create_reply_link(ticket_id, sent.message_id)
    await ticket_service.update_message_admin_id(user_message_db_id, sent.message_id)


async def _notify_admin_about_feedback(bot: Bot, config: Config, user: User, text: str) -> None:
    if config.admin_chat_id is None:
        return
    try:
        await bot.send_message(config.admin_chat_id, format_feedback_notice(user, text))
    except TelegramAPIError as exc:
        logger.warning("Failed to notify admin chat about feedback from %s: %s", user.id, exc)


def _callback_int_tail(data: str | None) -> int | None:
    if not data:
        return None
    raw = data.rsplit(":", 1)[-1]
    return int(raw) if raw.isdigit() else None
