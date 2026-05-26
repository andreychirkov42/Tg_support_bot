from collections.abc import Mapping, Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from .config import STATUS_EMOJI, STATUS_LABELS


CREATE_TICKET = "🆘 Создать обращение"
MY_TICKETS = "📋 Мои обращения"
FAQ = "❓ FAQ"
CONTACT_OPERATOR = "👨‍💻 Связаться с оператором"
ABOUT = "ℹ️ О сервисе"
MAIN_MENU = "🏠 Главное меню"
BACK = "🔙 Назад"

CATEGORIES = {
    "payment": "💳 Оплата",
    "order": "📦 Заказ",
    "tech": "🛠 Техническая проблема",
    "account": "🔐 Аккаунт",
    "other": "💬 Другое",
}

FAQ_QUESTIONS = {
    "payment": "Как оплатить?",
    "access": "Как восстановить доступ?",
    "order": "Где мой заказ?",
    "operator": "Как связаться с оператором?",
}


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=CREATE_TICKET), KeyboardButton(text=MY_TICKETS)],
            [KeyboardButton(text=FAQ), KeyboardButton(text=CONTACT_OPERATOR)],
            [KeyboardButton(text=ABOUT)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


def back_to_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=MAIN_MENU)]],
        resize_keyboard=True,
        input_field_placeholder="Напишите сообщение или вернитесь в меню",
    )


def categories_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=title, callback_data=f"ticket:category:{code}")]
        for code, title in CATEGORIES.items()
    ]
    rows.append([InlineKeyboardButton(text=BACK, callback_data="main:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ticket_preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отправить", callback_data="ticket:send")],
            [InlineKeyboardButton(text="✏️ Изменить текст", callback_data="ticket:edit_text")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="ticket:cancel")],
        ]
    )


def user_tickets_keyboard(tickets: Sequence[Mapping[str, object]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for ticket in tickets:
        status = str(ticket["status"])
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"#{ticket['id']} — {STATUS_EMOJI.get(status, '')} {STATUS_LABELS.get(status, status)}",
                    callback_data=f"ticket:detail:{ticket['id']}",
                )
            ]
        )

    rows.append([InlineKeyboardButton(text=BACK, callback_data="main:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def user_ticket_detail_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить статус", callback_data=f"ticket:refresh:{ticket_id}")],
            [InlineKeyboardButton(text="💬 Добавить сообщение", callback_data=f"ticket:add_message:{ticket_id}")],
            [InlineKeyboardButton(text=BACK, callback_data="ticket:list")],
            [InlineKeyboardButton(text=MAIN_MENU, callback_data="main:menu")],
        ]
    )


def faq_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=question, callback_data=f"faq:{code}")]
        for code, question in FAQ_QUESTIONS.items()
    ]
    rows.append([InlineKeyboardButton(text=BACK, callback_data="main:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def faq_answer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BACK, callback_data="faq:back")],
            [InlineKeyboardButton(text=MAIN_MENU, callback_data="main:menu")],
        ]
    )


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Новые обращения", callback_data="admin:list:new")],
            [InlineKeyboardButton(text="🔄 В работе", callback_data="admin:list:in_progress")],
            [InlineKeyboardButton(text="✅ Закрытые", callback_data="admin:list:closed")],
            [InlineKeyboardButton(text="🔍 Найти обращение", callback_data="admin:find")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
        ]
    )


def admin_ticket_list_keyboard(tickets: Sequence[Mapping[str, object]], status: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for ticket in tickets:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"#{ticket['id']} — {ticket['category']}",
                    callback_data=f"admin:ticket:{ticket['id']}",
                )
            ]
        )

    rows.append([InlineKeyboardButton(text=BACK, callback_data="admin:panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_ticket_actions_keyboard(ticket: Mapping[str, object]) -> InlineKeyboardMarkup:
    ticket_id = int(ticket["id"])
    status = str(ticket["status"])
    rows: list[list[InlineKeyboardButton]] = []

    if status != "in_progress":
        rows.append([InlineKeyboardButton(text="📌 Взять в работу", callback_data=f"admin:set_status:{ticket_id}:in_progress")])

    rows.append([InlineKeyboardButton(text="💬 Ответить пользователю", callback_data=f"admin:answer:{ticket_id}")])

    if status != "closed":
        rows.append([InlineKeyboardButton(text="✅ Закрыть обращение", callback_data=f"admin:set_status:{ticket_id}:closed")])

    rows.append([InlineKeyboardButton(text="🔁 Изменить статус", callback_data=f"admin:statuses:{ticket_id}")])
    rows.append([InlineKeyboardButton(text=BACK, callback_data="admin:panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_status_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🆕 Новое", callback_data=f"admin:set_status:{ticket_id}:new")],
            [InlineKeyboardButton(text="🔄 В работе", callback_data=f"admin:set_status:{ticket_id}:in_progress")],
            [InlineKeyboardButton(text="✅ Закрыто", callback_data=f"admin:set_status:{ticket_id}:closed")],
            [InlineKeyboardButton(text=BACK, callback_data=f"admin:ticket:{ticket_id}")],
        ]
    )

