from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def master_panel_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📋 Шаблон Недели"), KeyboardButton(text="📅 Мое Расписание")],
        [KeyboardButton(text="➕ Добавить Окошко"), KeyboardButton(text="📎 Другое")],
        [KeyboardButton(text="🔙 Главное Меню")]
    ], resize_keyboard=True)

def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="❌ Отмена")]
    ], resize_keyboard=True)
