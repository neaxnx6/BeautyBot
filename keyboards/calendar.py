"""
Inline-календарь для панели мастера
Месячная сетка с компактными индикаторами
"""
import calendar
from datetime import datetime
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import types

WEEKDAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MONTHS_RU = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
]


def build_month_calendar(year: int, month: int, days_with_free: set, days_with_booked: set) -> types.InlineKeyboardMarkup:
    """
    Build inline keyboard calendar for a given month.
    
    Indicators:
      📍26  = today (no slots)
      🟢26  = has free slots
      🔴26  = all booked (no free slots left)
      26    = no slots at all
      " "   = past days (unclickable empty cell)
    """
    kb = InlineKeyboardBuilder()
    
    today = datetime.now()
    
    # Calculate prev/next month for navigation
    prev_month, prev_year = (12, year - 1) if month == 1 else (month - 1, year)
    next_month, next_year = (1, year + 1) if month == 12 else (month + 1, year)
    
    # Header: [<] [Month Year] [>]
    month_text = f"{MONTHS_RU[month]} {year}" if year != today.year else f"{MONTHS_RU[month]}"
    kb.button(text="◀️", callback_data=f"cal_prev_{prev_year}-{prev_month:02d}")
    kb.button(text=month_text, callback_data="cal_ignore")
    kb.button(text="▶️", callback_data=f"cal_next_{next_year}-{next_month:02d}")
    
    # Weekday headers
    for day_name in WEEKDAYS_SHORT:
        kb.button(text=day_name, callback_data="cal_ignore")
    
    # Calendar grid
    cal = calendar.Calendar(firstweekday=0)
    today = datetime.now()
    month_days = cal.monthdayscalendar(year, month)
    
    for week in month_days:
        for day in week:
            if day == 0:
                kb.button(text=" ", callback_data="cal_ignore")
            else:
                date_str = f"{day:02d}.{month:02d}"
                is_today = (year == today.year and month == today.month and day == today.day)
                
                # Check if day is in the past
                is_past = False
                try:
                    day_dt = datetime(year, month, day, 23, 59)
                    if day_dt < today and not is_today:
                        is_past = True
                except:
                    pass
                
                has_free = day in days_with_free
                has_booked = day in days_with_booked
                
                if is_past:
                    # Past day - unclickable, number only
                    kb.button(text=f"{day}", callback_data="cal_past")
                else:
                    if has_free:
                        label = f"🟢{day}"
                    elif has_booked:
                        label = f"🔴{day}"
                    elif is_today:
                        label = f"📍{day}"
                    else:
                        label = f"{day}"
                    kb.button(text=label, callback_data=f"cal_day_{date_str}_{year}-{month:02d}")
    
    # Bottom actions
    kb.button(text="📋 Список", callback_data="schedule_list_view")
    
    # Layout
    sizes = [3, 7]  # header row (3 nav buttons) + weekday row (7)
    for _ in month_days:
        sizes.append(7)
    sizes.append(1)  # bottom list button
    
    kb.adjust(*sizes)
    return kb.as_markup()

def build_client_month_calendar(year: int, month: int, days_with_free: set) -> types.InlineKeyboardMarkup:
    """
    Build inline keyboard calendar for clients for a given month.
    
    Indicators:
      🟢26  = has free slots -> clickable
      26    = no free slots -> unclickable
      " "   = past days/empty cells -> unclickable
    """
    kb = InlineKeyboardBuilder()
    today = datetime.now()
    
    # Calculate prev/next month for navigation
    prev_month, prev_year = (12, year - 1) if month == 1 else (month - 1, year)
    next_month, next_year = (1, year + 1) if month == 12 else (month + 1, year)
    
    # Header: [<] [Month Year] [>]
    month_text = f"{MONTHS_RU[month]} {year}" if year != today.year else f"{MONTHS_RU[month]}"
    
    # Only allow going back if the previous month is not before the current month
    # To keep it simple, we can allow going back to current month if we are in future.
    can_go_back = (year > today.year) or (year == today.year and month > today.month)
    
    if can_go_back:
        kb.button(text="◀️", callback_data=f"client_cal_prev_{prev_year}-{prev_month:02d}")
    else:
        kb.button(text=" ", callback_data="cal_ignore")
        
    kb.button(text=month_text, callback_data="cal_ignore")
    kb.button(text="▶️", callback_data=f"client_cal_next_{next_year}-{next_month:02d}")
    
    # Weekday headers
    for day_name in WEEKDAYS_SHORT:
        kb.button(text=day_name, callback_data="cal_ignore")
    
    # Calendar grid
    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(year, month)
    
    for week in month_days:
        for day in week:
            if day == 0:
                kb.button(text=" ", callback_data="cal_ignore")
            else:
                date_str = f"{day:02d}.{month:02d}"
                is_today = (year == today.year and month == today.month and day == today.day)
                
                # Check if day is in the past
                is_past = False
                try:
                    day_dt = datetime(year, month, day, 23, 59)
                    if day_dt < today and not is_today:
                        is_past = True
                except:
                    pass
                
                has_free = day in days_with_free
                
                if is_past:
                    # Past day - unclickable
                    kb.button(text=f"{day}", callback_data="cal_ignore")
                elif has_free:
                    # Has free slots - clickable
                    kb.button(text=f"🟢 {day}", callback_data=f"day_{date_str}")
                else:
                    # No free slots - unclickable
                    kb.button(text=f"{day}", callback_data="cal_ignore")
    
    # Add back button
    kb.button(text="⬅️ Назад", callback_data="back_from_slots")
    
    # Layout sizes
    sizes = [3, 7]  # Header (3) + Weekdays (7)
    for _ in month_days:
        sizes.append(7)
    sizes.append(1) # Back button
    
    kb.adjust(*sizes)
    return kb.as_markup()

