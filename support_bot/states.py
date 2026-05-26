from aiogram.fsm.state import State, StatesGroup


class CreateTicket(StatesGroup):
    choosing_category = State()
    waiting_text = State()
    preview = State()
    waiting_operator_text = State()


class AddTicketMessage(StatesGroup):
    waiting_text = State()


class AdminAnswer(StatesGroup):
    waiting_text = State()


class AdminSearch(StatesGroup):
    waiting_ticket_id = State()

