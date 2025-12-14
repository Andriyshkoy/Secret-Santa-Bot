from aiogram.fsm.state import State, StatesGroup


class RegistrationState(StatesGroup):
    waiting_for_name = State()
    waiting_for_wishes = State()
    waiting_for_registered_action = State()
    waiting_for_new_name = State()
