from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu_kb(is_master=False):
    kb = [
        [KeyboardButton(text="💅 Записаться")],
        [KeyboardButton(text="👤 Мои записи")]
    ]
    if is_master:
        kb.append([KeyboardButton(text="⚙️ Панель Мастера")])
    
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
