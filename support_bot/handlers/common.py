from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..keyboards import main_menu_keyboard


router = Router(name="common")


@router.message(Command("menu"))
async def menu_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Открыл главное меню.", reply_markup=main_menu_keyboard())


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "Используйте кнопки меню, чтобы создать обращение, посмотреть FAQ или связаться с оператором.",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data)
async def unknown_callback(callback: CallbackQuery) -> None:
    await callback.answer("Действие устарело. Откройте меню заново.", show_alert=True)


@router.message()
async def unknown_message(message: Message) -> None:
    await message.answer(
        "Я не понял сообщение. Пожалуйста, выберите действие в меню.",
        reply_markup=main_menu_keyboard(),
    )

