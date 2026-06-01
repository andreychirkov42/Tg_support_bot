import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from .config import load_config
from .database import Database
from .handlers import admin_channel, common, user
from .services.admin_service import AdminService
from .services.feedback_service import FeedbackService
from .services.ticket_service import TicketService
from .services.user_service import UserService


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = load_config()
    if config.admin_chat_id is None:
        logging.warning("ADMIN_CHAT_ID is empty. User ticket creation will be disabled.")
    if not config.admin_ids:
        logging.warning("ADMIN_IDS is empty. Admin buttons will be inaccessible.")

    database = Database(config.database_path)
    await database.connect()
    await database.init_schema()

    user_service = UserService(database)
    ticket_service = TicketService(database, user_service)
    admin_service = AdminService(database)
    feedback_service = FeedbackService(database, user_service)

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())

    dispatcher["config"] = config
    dispatcher["user_service"] = user_service
    dispatcher["ticket_service"] = ticket_service
    dispatcher["admin_service"] = admin_service
    dispatcher["feedback_service"] = feedback_service

    dispatcher.include_router(admin_channel.router)
    dispatcher.include_router(user.router)
    dispatcher.include_router(common.router)

    try:
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        await database.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
