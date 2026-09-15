from aiogram.fsm.state import State, StatesGroup


class ReminderFlow(StatesGroup):
    waiting_confirmation = State()
