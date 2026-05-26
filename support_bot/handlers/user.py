from datetime import datetime
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..config import Config, STATUS_EMOJI, STATUS_LABELS
from ..keyboards import (
    ABOUT,
    BACK,
    CATEGORIES,
    CONTACT_OPERATOR,
    CREATE_TICKET,
    FAQ,
    FAQ_QUESTIONS,
    MAIN_MENU,
    MY_TICKETS,
    back_to_menu_keyboard,
    categories_keyboard,
    faq_answer_keyboard,
    faq_keyboard,
    main_menu_keyboard,
    ticket_preview_keyboard,
    user_ticket_detail_keyboard,
    user_tickets_keyboard,
)
from ..services.ticket_service import TicketService
from ..states import AddTicketMessage, CreateTicket
from .admin import format_admin_ticket


router = Router(name="user")

FAQ_ANSWERS = {
    "payment": "Оплатить можно банковской картой или другим способом, который доступен на странице оплаты. Если платеж не прошел, создайте обращение в категории «Оплата».",
    "access": "Для восстановления доступа используйте форму входа и кнопку восстановления. Если письмо не пришло, напишите нам категорию «Аккаунт».",
    "order": "Статус заказа обычно обновляется автоматически. Если обновления давно нет, создайте обращение в категории «Заказ» и укажите номер заказа.",
    "operator": "Нажмите «Связаться с оператором» в главном меню, опишите вопрос, и специалист ответит вам в Telegram.",
}


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, ticket_service: TicketService) -> None:
    await state.clear()
    if message.from_user is not None:
        await ticket_service.ensure_user(message.from_user)

    await message.answer(
        "Здравствуйте! 👋\n\nЯ бот службы поддержки. Выберите нужный раздел в меню ниже.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text.in_({MAIN_MENU, BACK}))
async def show_main_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Главное меню открыто. Чем помочь?", reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "main:menu")
async def show_main_menu_from_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.answer("Главное меню открыто. Чем помочь?", reply_markup=main_menu_keyboard())


@router.message(F.text == CREATE_TICKET)
async def create_ticket_start(message: Message, state: FSMContext) -> None:
    await state.set_state(CreateTicket.choosing_category)
    await message.answer(
        "Выберите тему обращения:",
        reply_markup=categories_keyboard(),
    )


@router.callback_query(StateFilter(CreateTicket.choosing_category), F.data.startswith("ticket:category:"))
async def choose_ticket_category(callback: CallbackQuery, state: FSMContext) -> None:
    category_code = callback.data.rsplit(":", 1)[-1]
    category = CATEGORIES.get(category_code)
    if category is None:
        await callback.answer("Неизвестная категория", show_alert=True)
        return

    await state.update_data(category=category, created_at=datetime.now().strftime("%d.%m.%Y %H:%M"))
    await state.set_state(CreateTicket.waiting_text)
    await callback.answer()
    await callback.message.answer(
        f"Тема: {category}\n\nОпишите проблему одним сообщением.",
        reply_markup=back_to_menu_keyboard(),
    )


@router.message(StateFilter(CreateTicket.waiting_text), F.text)
async def receive_ticket_text(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if len(text) < 5:
        await message.answer("Добавьте чуть больше деталей, чтобы мы быстрее помогли.")
        return

    await state.update_data(text=text)
    data = await state.get_data()
    await state.set_state(CreateTicket.preview)

    await message.answer(
        _format_ticket_preview(data["category"], text, data["created_at"]),
        reply_markup=ticket_preview_keyboard(),
    )


@router.message(StateFilter(CreateTicket.waiting_text))
async def receive_ticket_text_invalid(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте описание проблемы текстом.")


@router.callback_query(StateFilter(CreateTicket.preview), F.data == "ticket:edit_text")
async def edit_ticket_text(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CreateTicket.waiting_text)
    await callback.answer()
    await callback.message.answer("Хорошо, отправьте новый текст обращения.", reply_markup=back_to_menu_keyboard())


@router.callback_query(StateFilter(CreateTicket.preview), F.data == "ticket:cancel")
async def cancel_ticket(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Обращение отменено")
    await callback.message.answer("Обращение отменено. Возвращаю в главное меню.", reply_markup=main_menu_keyboard())


@router.callback_query(StateFilter(CreateTicket.preview), F.data == "ticket:send")
async def send_ticket(
    callback: CallbackQuery,
    state: FSMContext,
    ticket_service: TicketService,
    bot: Bot,
    config: Config,
) -> None:
    if callback.from_user is None:
        await callback.answer("Не удалось определить пользователя", show_alert=True)
        return

    data = await state.get_data()
    ticket_id = await ticket_service.create_ticket(callback.from_user, data["category"], data["text"])
    await state.clear()
    await callback.answer("Обращение отправлено")
    await callback.message.answer(
        f"✅ Обращение #{ticket_id} создано.\n\n"
        "Автоответ: мы получили ваш запрос и уже передали его в поддержку. "
        "Статус можно проверить в разделе «Мои обращения».",
        reply_markup=main_menu_keyboard(),
    )
    await _notify_admins(bot, config, ticket_service, ticket_id)


@router.message(F.text == CONTACT_OPERATOR)
async def contact_operator_start(message: Message, state: FSMContext) -> None:
    await state.set_state(CreateTicket.waiting_operator_text)
    await message.answer(
        "Опишите вопрос для оператора. Я создам обращение и передам его специалисту.",
        reply_markup=back_to_menu_keyboard(),
    )


@router.message(StateFilter(CreateTicket.waiting_operator_text), F.text)
async def contact_operator_text(
    message: Message,
    state: FSMContext,
    ticket_service: TicketService,
    bot: Bot,
    config: Config,
) -> None:
    if message.from_user is None:
        await message.answer("Не удалось определить пользователя. Попробуйте открыть меню через /start.")
        return

    text = message.text.strip()
    if len(text) < 3:
        await message.answer("Напишите вопрос чуть подробнее.")
        return

    ticket_id = await ticket_service.create_ticket(message.from_user, "Оператор", text)
    await state.clear()
    await message.answer(
        f"👨‍💻 Обращение #{ticket_id} создано.\n\nОператор скоро ответит вам.",
        reply_markup=main_menu_keyboard(),
    )
    await _notify_admins(bot, config, ticket_service, ticket_id)


@router.message(StateFilter(CreateTicket.waiting_operator_text))
async def contact_operator_invalid(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте вопрос текстом.")


@router.message(F.text == MY_TICKETS)
async def my_tickets(message: Message, ticket_service: TicketService) -> None:
    if message.from_user is None:
        return
    await _send_user_tickets(message, ticket_service, message.from_user.id)


@router.callback_query(F.data == "ticket:list")
async def my_tickets_callback(callback: CallbackQuery, ticket_service: TicketService) -> None:
    await callback.answer()
    await _send_user_tickets(callback.message, ticket_service, callback.from_user.id)


@router.callback_query(F.data.startswith("ticket:detail:"))
async def show_ticket_detail(callback: CallbackQuery, ticket_service: TicketService) -> None:
    ticket_id = int(callback.data.rsplit(":", 1)[-1])
    ticket = await ticket_service.get_ticket_for_user(ticket_id, callback.from_user.id)
    await callback.answer()

    if ticket is None:
        await callback.message.answer("Обращение не найдено или недоступно.")
        return

    await callback.message.answer(
        _format_user_ticket(ticket),
        reply_markup=user_ticket_detail_keyboard(ticket_id),
    )


@router.callback_query(F.data.startswith("ticket:refresh:"))
async def refresh_ticket_status(callback: CallbackQuery, ticket_service: TicketService) -> None:
    ticket_id = int(callback.data.rsplit(":", 1)[-1])
    ticket = await ticket_service.get_ticket_for_user(ticket_id, callback.from_user.id)
    if ticket is None:
        await callback.answer("Обращение не найдено", show_alert=True)
        return

    await callback.answer("Статус обновлен")
    await callback.message.answer(
        _format_user_ticket(ticket),
        reply_markup=user_ticket_detail_keyboard(ticket_id),
    )


@router.callback_query(F.data.startswith("ticket:add_message:"))
async def add_ticket_message_start(callback: CallbackQuery, state: FSMContext, ticket_service: TicketService) -> None:
    ticket_id = int(callback.data.rsplit(":", 1)[-1])
    ticket = await ticket_service.get_ticket_for_user(ticket_id, callback.from_user.id)
    if ticket is None:
        await callback.answer("Обращение не найдено", show_alert=True)
        return

    await state.update_data(ticket_id=ticket_id)
    await state.set_state(AddTicketMessage.waiting_text)
    await callback.answer()
    await callback.message.answer("Напишите дополнительное сообщение по обращению.", reply_markup=back_to_menu_keyboard())


@router.message(StateFilter(AddTicketMessage.waiting_text), F.text)
async def add_ticket_message(
    message: Message,
    state: FSMContext,
    ticket_service: TicketService,
    bot: Bot,
    config: Config,
) -> None:
    if message.from_user is None:
        return

    data = await state.get_data()
    ticket_id = int(data["ticket_id"])
    ticket = await ticket_service.get_ticket_for_user(ticket_id, message.from_user.id)
    if ticket is None:
        await state.clear()
        await message.answer("Обращение не найдено. Возвращаю в меню.", reply_markup=main_menu_keyboard())
        return

    await ticket_service.add_message(ticket_id, "user", message.from_user.id, message.text.strip())
    await state.clear()
    await message.answer("💬 Сообщение добавлено к обращению.", reply_markup=main_menu_keyboard())
    await _notify_admins_about_user_message(bot, config, ticket_service, ticket_id)


@router.message(StateFilter(AddTicketMessage.waiting_text))
async def add_ticket_message_invalid(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте сообщение текстом.")


@router.message(F.text == FAQ)
async def faq(message: Message) -> None:
    await message.answer("Выберите вопрос:", reply_markup=faq_keyboard())


@router.callback_query(F.data == "faq:back")
async def faq_back(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer("Выберите вопрос:", reply_markup=faq_keyboard())


@router.callback_query(F.data.startswith("faq:"))
async def faq_answer(callback: CallbackQuery) -> None:
    key = callback.data.rsplit(":", 1)[-1]
    question = FAQ_QUESTIONS.get(key)
    answer = FAQ_ANSWERS.get(key)

    if question is None or answer is None:
        await callback.answer("Ответ не найден", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer(
        f"❓ <b>{escape(question)}</b>\n\n{escape(answer)}",
        reply_markup=faq_answer_keyboard(),
    )


@router.message(F.text == ABOUT)
async def about(message: Message) -> None:
    await message.answer(
        "ℹ️ <b>О сервисе</b>\n\n"
        "Этот бот помогает быстро отправить вопрос в поддержку, получить автоответ "
        "и отслеживать статус обращения без лишних команд.",
        reply_markup=main_menu_keyboard(),
    )


async def _send_user_tickets(message: Message, ticket_service: TicketService, telegram_id: int) -> None:
    tickets = await ticket_service.get_user_tickets(telegram_id)
    if not tickets:
        await message.answer(
            "У вас пока нет обращений. Можно создать первое через главное меню.",
            reply_markup=main_menu_keyboard(),
        )
        return

    await message.answer("Ваши обращения:", reply_markup=user_tickets_keyboard(tickets))


async def _notify_admins(bot: Bot, config: Config, ticket_service: TicketService, ticket_id: int) -> None:
    if not config.admin_ids:
        return

    ticket = await ticket_service.get_ticket(ticket_id)
    if ticket is None:
        return

    for admin_id in config.admin_ids:
        try:
            await bot.send_message(admin_id, "📥 Новое обращение\n\n" + format_admin_ticket(ticket))
        except TelegramAPIError:
            continue


async def _notify_admins_about_user_message(
    bot: Bot,
    config: Config,
    ticket_service: TicketService,
    ticket_id: int,
) -> None:
    if not config.admin_ids:
        return

    ticket = await ticket_service.get_ticket(ticket_id)
    if ticket is None:
        return

    for admin_id in config.admin_ids:
        try:
            await bot.send_message(admin_id, "💬 Новое сообщение от пользователя\n\n" + format_admin_ticket(ticket))
        except TelegramAPIError:
            continue


def _format_ticket_preview(category: str, text: str, created_at: str) -> str:
    return (
        "📄 <b>Предпросмотр обращения</b>\n\n"
        f"<b>Категория:</b> {escape(category)}\n"
        f"<b>Текст:</b> {escape(text)}\n"
        f"<b>Дата:</b> {escape(created_at)}\n"
        f"<b>Статус:</b> {STATUS_EMOJI['new']} {STATUS_LABELS['new']}"
    )


def _format_user_ticket(ticket) -> str:
    status = str(ticket["status"])
    return (
        f"📌 <b>Обращение #{ticket['id']}</b>\n\n"
        f"<b>Категория:</b> {escape(str(ticket['category']))}\n"
        f"<b>Текст:</b> {escape(str(ticket['text']))}\n"
        f"<b>Статус:</b> {STATUS_EMOJI.get(status, '')} {STATUS_LABELS.get(status, status)}\n"
        f"<b>Дата создания:</b> {escape(_human_datetime(str(ticket['created_at'])))}"
    )


def _human_datetime(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return value

