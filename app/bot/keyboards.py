from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

PARTICIPATE_BTN = "🎅 Участвовать"
WISHES_BTN = "🎁 Мои пожелания"
RULES_BTN = "📜 Правила"
RECIPIENT_BTN = "🎄 Кто мне выпал"
CHANGE_NAME_BTN = "✏️ Изменить имя"
BACK_BTN = "↩️ Назад"
ADMIN_BTN = "🛠 Админ"
ADMIN_SHUFFLE_BTN = "🎲 Распределить"
ADMIN_LIST_BTN = "📋 Список"
ADMIN_BACK_BTN = "⬅️ В меню"
CANCEL_PARTICIPATION_BTN = "🚫 Отказаться"


def main_keyboard(shuffle_done: bool, is_admin: bool = False) -> ReplyKeyboardMarkup:
    primary = RECIPIENT_BTN if shuffle_done else PARTICIPATE_BTN
    actions = [
        [KeyboardButton(text=primary)],
        [KeyboardButton(text=WISHES_BTN)],
        [KeyboardButton(text=RULES_BTN)],
    ]
    if is_admin:
        actions.append([KeyboardButton(text=ADMIN_BTN)])
    return ReplyKeyboardMarkup(
        keyboard=actions,
        resize_keyboard=True,
        input_field_placeholder="Выбери действие",
    )


def admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADMIN_SHUFFLE_BTN)],
            [KeyboardButton(text=ADMIN_LIST_BTN)],
            [KeyboardButton(text=ADMIN_BACK_BTN)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Админ-действие",
    )
