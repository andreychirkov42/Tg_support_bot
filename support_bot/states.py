from aiogram.fsm.state import State, StatesGroup


class CreateTicket(StatesGroup):
    choosing_category = State()
    waiting_text = State()
    preview = State()


class AddTicketMessage(StatesGroup):
    waiting_text = State()
