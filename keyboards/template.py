from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

WEEKDAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

def weekly_template_kb(day_counts: dict):
    """Main weekly template menu with day counters
    day_counts: {0: 3, 1: 2, ...} - number of slots per day
    """
    kb = InlineKeyboardBuilder()
    
    # Days with counters (4 per row)
    for day in range(7):
        count = day_counts.get(day, 0)
        kb.button(text=f"{WEEKDAYS_SHORT[day]} ({count})", callback_data=f"day_{day}")
    
    # Action button
    kb.button(text="🔄 Сгенерировать окошки", callback_data="template_generate")
    
    # Layout: 4 days, 3 days, 1 generation button
    kb.adjust(4, 3, 1)
    
    return kb.as_markup()

def day_time_selector_kb(day_of_week: int, selected_times: list):
    """Time selection with checkboxes
    selected_times: ["09:00", "13:00", ...] - currently selected
    """
    kb = InlineKeyboardBuilder()
    
    # Generate times 9:00-20:30
    for hour in range(9, 21):
        for minute in [0, 30]:
            if hour == 20 and minute == 30:
                continue
            
            time_str = f"{hour:02d}:{minute:02d}"
            emoji = "✅" if time_str in selected_times else "❌"
            kb.button(
                text=f"{emoji} {time_str}", 
                callback_data=f"toggle_time_{day_of_week}_{time_str}"
            )
    
    # Action buttons
    kb.button(text="✅ Подтвердить", callback_data=f"confirm_times_{day_of_week}")
    kb.button(text="⬅️ Назад", callback_data="back_to_template")
    
    # Layout: times in rows of 4, then confirm/back together
    # Total buttons: ~23 time buttons + 2 action = 25
    # 4,4,4,4,4,3,2 = 25 buttons
    kb.adjust(4, 4, 4, 4, 4, 3, 2)
    
    return kb.as_markup()

def generation_period_kb():
    """Period selection for slot generation"""
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 1 неделя", callback_data="gen_7")
    kb.button(text="📅 2 недели", callback_data="gen_14")
    kb.button(text="📅 1 месяц", callback_data="gen_30")
    kb.button(text="⬅️ Назад", callback_data="back_to_template")
    kb.adjust(1)
    return kb.as_markup()

def vacation_management_kb():
    """Vacation days management"""
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить выходной", callback_data="add_vacation")
    kb.button(text="🗑 Удалить выходной", callback_data="del_vacation")
    kb.button(text="⬅️ Назад", callback_data="back_to_template")
    kb.adjust(1)
    return kb.as_markup()

def other_menu_kb():
    """Other menu (link + min time)"""
    kb = InlineKeyboardBuilder()
    kb.button(text="🔗 Моя ссылка для записи", callback_data="my_link")
    kb.button(text="⏰ Мин. время до записи", callback_data="template_min_time")
    kb.button(text="⬅️ Назад", callback_data="back_to_master_panel")
    kb.adjust(1)
    return kb.as_markup()

def min_booking_time_kb():
    """Minimum booking time settings"""
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отключить", callback_data="mintime_0")
    kb.button(text="6 часов", callback_data="mintime_6")
    kb.button(text="12 часов", callback_data="mintime_12")
    kb.button(text="24 часа", callback_data="mintime_24")
    kb.button(text="48 часов", callback_data="mintime_48")
    kb.button(text="⬅️ Назад", callback_data="back_to_other")
    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()
