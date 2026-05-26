from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from .config import Config
from .utils.permissions import is_admin_id


class AdminOnly(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery, config: Config) -> bool:
        user = event.from_user
        return user is not None and is_admin_id(user.id, config)


class AdminChatOnly(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery, config: Config) -> bool:
        chat_id = None
        if isinstance(event, Message):
            chat_id = event.chat.id
        elif event.message is not None:
            chat_id = event.message.chat.id
        return config.admin_chat_id is not None and chat_id == config.admin_chat_id
