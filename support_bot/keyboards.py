from collections.abc import Mapping, Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from .config import STATUS_EMOJI, STATUS_LABELS


CREATE_TICKET = "🆘 Создать обращение"
MY_TICKETS = "📋 Мои обращения"
MAIN_MENU = "🏠 Главное меню"
BACK = "🔙 Назад"

CATEGORIES = {
    "payment": "💳 Оплата",
    "order": "📦 Заказ",
    "tech": "🛠 Техническая проблема",
    "account": "🔐 Аккаунт",
    "other": "💬 Другое",
}

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=CREATE_TICKET), KeyboardButton(text=MY_TICKETS)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


def back_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BACK), KeyboardButton(text=MAIN_MENU)]],
        resize_keyboard=True,
        input_field_placeholder="Напишите сообщение",
    )


def categories_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=title, callback_data=f"u:cat:{code}")]
        for code, title in CATEGORIES.items()
    ]
    rows.append([InlineKeyboardButton(text=BACK, callback_data="u:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ticket_preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отправить", callback_data="u:ticket:send")],
            [InlineKeyboardButton(text="✏️ Изменить текст", callback_data="u:ticket:edit")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="u:ticket:cancel")],
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
                    callback_data=f"u:t:{ticket['id']}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text=BACK, callback_data="u:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def user_ticket_detail_keyboard(ticket_id: int, status: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🔄 Обновить статус", callback_data=f"u:refresh:{ticket_id}")],
    ]
    if status != "closed":
        rows.append([InlineKeyboardButton(text="💬 Добавить сообщение", callback_data=f"u:add:{ticket_id}")])
    rows.extend(
        [
            [InlineKeyboardButton(text=BACK, callback_data="u:tickets")],
            [InlineKeyboardButton(text=MAIN_MENU, callback_data="u:menu")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Новые обращения", callback_data="a:list:new")],
            [InlineKeyboardButton(text="🟡 В работе", callback_data="a:list:in_progress")],
            [InlineKeyboardButton(text="✅ Закрытые", callback_data="a:list:closed")],
            [InlineKeyboardButton(text="🔍 Найти обращение", callback_data="a:find")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="a:stats")],
        ]
    )


def admin_ticket_keyboard(ticket: Mapping[str, object]) -> InlineKeyboardMarkup:
    ticket_id = int(ticket["id"])
    telegram_id = int(ticket["telegram_id"])
    status = str(ticket["status"])
    is_blocked = bool(ticket["is_blocked"])

    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="👁 Открыть", callback_data=f"a:open:{ticket_id}")],
    ]
    if status != "in_progress":
        rows.append([InlineKeyboardButton(text="🟡 Взять в работу", callback_data=f"a:work:{ticket_id}")])
    rows.append([InlineKeyboardButton(text="💬 Ответить", callback_data=f"a:answer:{ticket_id}")])
    if status != "closed":
        rows.append([InlineKeyboardButton(text="✅ Закрыть", callback_data=f"a:close:{ticket_id}")])
    if is_blocked:
        rows.append([InlineKeyboardButton(text="✅ Разблокировать пользователя", callback_data=f"a:unblock:{telegram_id}:{ticket_id}")])
    else:
        rows.append([InlineKeyboardButton(text="🚫 Заблокировать пользователя", callback_data=f"a:block:{telegram_id}:{ticket_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_message_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💬 Ответить", callback_data=f"a:answer:{ticket_id}")],
            [InlineKeyboardButton(text="✅ Закрыть", callback_data=f"a:close:{ticket_id}")],
            [InlineKeyboardButton(text="👁 История", callback_data=f"a:open:{ticket_id}")],
        ]
    )


def admin_ticket_list_keyboard(tickets: Sequence[Mapping[str, object]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for ticket in tickets:
        status = str(ticket["status"])
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"#{ticket['id']} — {STATUS_EMOJI.get(status, '')} {ticket['category']}",
                    callback_data=f"a:open:{ticket['id']}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="🛠 Панель поддержки", callback_data="a:panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
