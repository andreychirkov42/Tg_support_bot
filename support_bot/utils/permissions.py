from aiogram.types import CallbackQuery, Message

from ..config import Config


def is_admin_id(user_id: int | None, config: Config) -> bool:
    return user_id is not None and user_id in config.admin_ids


def is_admin_chat_id(chat_id: int | None, config: Config) -> bool:
    return config.admin_chat_id is not None and chat_id == config.admin_chat_id


def is_admin_message(message: Message, config: Config) -> bool:
    if not is_admin_chat_id(message.chat.id, config):
        return False
    if message.from_user is None:
        return message.chat.type == "channel"
    return is_admin_id(message.from_user.id, config)


def is_admin_callback(callback: CallbackQuery, config: Config) -> bool:
    if callback.message is None or not is_admin_chat_id(callback.message.chat.id, config):
        return False
    return is_admin_id(callback.from_user.id if callback.from_user else None, config)
