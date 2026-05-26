from collections.abc import Mapping, Sequence
from datetime import datetime
from html import escape

from ..config import STATUS_EMOJI, STATUS_LABELS


def html(value: object) -> str:
    return escape("" if value is None else str(value), quote=False)


def code(value: object) -> str:
    return f"<code>{html(value)}</code>"


def human_dt(value: object) -> str:
    raw = "" if value is None else str(value)
    try:
        return datetime.fromisoformat(raw).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return raw


def cut_text(text: object, limit: int = 1200) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1].rstrip()}…"


def status_text(status: str) -> str:
    return f"{STATUS_EMOJI.get(status, '')} {STATUS_LABELS.get(status, status)}".strip()


def format_ticket_preview(category: str, text: str, created_at: str) -> str:
    return (
        "📄 <b>Предпросмотр обращения</b>\n\n"
        f"<b>Категория:</b> {html(category)}\n"
        f"<b>Текст:</b>\n{html(cut_text(text, 900))}\n\n"
        f"<b>Дата:</b> {html(created_at)}\n"
        f"<b>Статус:</b> {status_text('new')}"
    )


def format_user_ticket(ticket: Mapping[str, object]) -> str:
    status = str(ticket["status"])
    return (
        f"📌 <b>Обращение #{ticket['id']}</b>\n\n"
        f"<b>Категория:</b> {html(ticket['category'])}\n"
        f"<b>Текст:</b>\n{html(cut_text(ticket['text'], 900))}\n\n"
        f"<b>Статус:</b> {status_text(status)}\n"
        f"<b>Дата создания:</b> {html(human_dt(ticket['created_at']))}"
    )


def format_admin_ticket(ticket: Mapping[str, object], *, title: str | None = None) -> str:
    status = str(ticket["status"])
    username = f"@{ticket['username']}" if ticket["username"] else "без username"
    heading = title or f"{STATUS_EMOJI.get(status, '📌')} <b>Обращение #{ticket['id']}</b>"
    return (
        f"{heading}\n\n"
        "👤 <b>Пользователь:</b>\n"
        f"• Имя: {html(ticket['first_name'] or 'Без имени')}\n"
        f"• Username: {html(username)}\n"
        f"• Telegram ID: {code(ticket['telegram_id'])}\n\n"
        "📂 <b>Категория:</b>\n"
        f"{html(ticket['category'])}\n\n"
        "📝 <b>Сообщение:</b>\n"
        f"{html(cut_text(ticket['text'], 1600))}\n\n"
        "📌 <b>Статус:</b>\n"
        f"{status_text(status)}\n\n"
        "🕒 <b>Дата:</b>\n"
        f"{html(human_dt(ticket['created_at']))}"
    )


def format_user_message_notice(ticket: Mapping[str, object], text: str) -> str:
    username = f"@{ticket['username']}" if ticket["username"] else "без username"
    return (
        f"📩 <b>Новое сообщение по обращению #{ticket['id']}</b>\n\n"
        "👤 <b>Пользователь:</b>\n"
        f"• {html(ticket['first_name'] or 'Без имени')} ({html(username)})\n"
        f"• Telegram ID: {code(ticket['telegram_id'])}\n\n"
        "📝 <b>Сообщение:</b>\n"
        f"{html(cut_text(text, 1600))}"
    )


def format_ticket_history(ticket: Mapping[str, object], messages: Sequence[Mapping[str, object]]) -> str:
    lines = [format_admin_ticket(ticket, title=f"👁 <b>История обращения #{ticket['id']}</b>")]
    if not messages:
        lines.append("\n\nИстория сообщений пока пустая.")
        return "".join(lines)

    lines.append("\n\n💬 <b>История:</b>")
    for item in messages:
        sender = str(item["sender_type"])
        label = {"user": "Пользователь", "admin": "Админ", "system": "Система"}.get(sender, sender)
        lines.append(
            "\n\n"
            f"<b>{html(label)}</b> · {html(human_dt(item['created_at']))}\n"
            f"{html(cut_text(item['text'], 650))}"
        )
    return "".join(lines)


def format_stats(stats: Mapping[str, int]) -> str:
    return (
        "📊 <b>Статистика поддержки</b>\n\n"
        f"Всего обращений: <b>{stats.get('total', 0)}</b>\n"
        f"Новых: <b>{stats.get('new', 0)}</b>\n"
        f"В работе: <b>{stats.get('in_progress', 0)}</b>\n"
        f"Закрытых: <b>{stats.get('closed', 0)}</b>\n"
        f"Пользователей: <b>{stats.get('users', 0)}</b>\n"
        f"Заблокированных: <b>{stats.get('blocked_users', 0)}</b>"
    )
