from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..config import Config
from ..keyboards import main_menu_keyboard
from ..utils.permissions import is_admin_chat_id


router = Router(name="common")


@router.message(Command("admin"))
async def admin_only_in_work_chat(message: Message, config: Config) -> None:
    if not is_admin_chat_id(message.chat.id, config):
        await message.answer("Админ-панель доступна только в рабочем канале поддержки.")


@router.message(Command("menu"))
async def menu_command(message: Message, state: FSMContext, config: Config) -> None:
    if is_admin_chat_id(message.chat.id, config):
        return
    await state.clear()
    await message.answer("Открыл главное меню.", reply_markup=main_menu_keyboard())


@router.message(Command("help"))
async def help_command(message: Message, config: Config) -> None:
    if is_admin_chat_id(message.chat.id, config):
        return
    await message.answer(
        "Используйте кнопки меню, чтобы создать обращение или посмотреть свои обращения.",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data)
async def unknown_callback(callback: CallbackQuery) -> None:
    await callback.answer("Действие устарело. Откройте меню заново.", show_alert=True)


@router.message()
async def unknown_message(message: Message, config: Config) -> None:
    if is_admin_chat_id(message.chat.id, config):
        return
    await message.answer(
        "Я не понял сообщение. Пожалуйста, выберите действие в меню.",
        reply_markup=main_menu_keyboard(),
    )
