from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def master_panel_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🗓 Шаблон"), KeyboardButton(text="📅 Расписание")],
        [KeyboardButton(text="✅ Добавить время"), KeyboardButton(text="⚙️ Настройки")],
        [KeyboardButton(text="🏠 Главное меню")]
    ], resize_keyboard=True)

def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="❌ Отмена")]
    ], resize_keyboard=True)
