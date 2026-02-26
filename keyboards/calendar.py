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
    
    Indicators (compact, no emoji):
      [26]  = today
      26·   = has free slots
      26✕   = all booked (no free slots left)
      26    = no slots at all
      past days = unclickable
    """
    kb = InlineKeyboardBuilder()
    
    # Header: month name + year
    kb.button(text=f"📅 {MONTHS_RU[month]} {year}", callback_data="cal_ignore")
    
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
                is_past = False
                
                # Check if day is in the past
                try:
                    day_dt = datetime(year, month, day, 23, 59)
                    if day_dt < today and not is_today:
                        is_past = True
                except:
                    pass
                
                has_free = day in days_with_free
                has_booked = day in days_with_booked
                
                if is_past:
                    # Past day - unclickable, dimmed
                    kb.button(text=f"  {day}  ", callback_data="cal_ignore")
                elif is_today:
                    if has_free:
                        label = f"[{day}·]"
                    elif has_booked:
                        label = f"[{day}✕]"
                    else:
                        label = f"[{day}]"
                    kb.button(text=label, callback_data=f"cal_day_{date_str}")
                elif has_free:
                    kb.button(text=f"{day}·", callback_data=f"cal_day_{date_str}")
                elif has_booked:
                    kb.button(text=f"{day}✕", callback_data=f"cal_day_{date_str}")
                else:
                    kb.button(text=f"{day}", callback_data=f"cal_day_{date_str}")
    
    # Navigation row
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1
    
    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1
    
    kb.button(text="◀️", callback_data=f"cal_prev_{prev_year}-{prev_month:02d}")
    kb.button(text="📋 Список", callback_data="schedule_list_view")
    kb.button(text="▶️", callback_data=f"cal_next_{next_year}-{next_month:02d}")
    
    # Layout
    sizes = [1, 7]
    for week in month_days:
        sizes.append(7)
    sizes.append(3)
    
    kb.adjust(*sizes)
    return kb.as_markup()
