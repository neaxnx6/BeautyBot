from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def master_panel_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🗓 Шаблон недели")],
        [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="🏠 Главное меню")]
    ], resize_keyboard=True)

def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="❌ Отмена")]
    ], resize_keyboard=True)

def build_date_keyboard():
    """Build date selection keyboard for 14 days."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from datetime import datetime, timedelta
    
    kb = InlineKeyboardBuilder()
    today = datetime.now()
    
    # Weekday constants (inside to avoid global mess)
    WEEKDAYS_FULL = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    for i in range(14):
        date = today + timedelta(days=i)
        weekday = WEEKDAYS_FULL[date.weekday()]
        
        date_str = date.strftime("%d.%m")
        full_date_str = date.strftime("%Y-%m-%d")
        
        label = f"{date_str} ({weekday})"
        if i == 0: label = "Сегодня"
        elif i == 1: label = "Завтра"
            
        kb.button(text=label, callback_data=f"date_{full_date_str}")
        
    kb.button(text="❌ Отмена", callback_data="cancel_slot")
    kb.adjust(2)
    return kb
