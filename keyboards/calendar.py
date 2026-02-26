"""
Inline-календарь для панели мастера
Месячная сетка с подсветкой дней
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
    
    Args:
        year: Year
        month: Month (1-12)
        days_with_free: Set of day numbers that have free slots
        days_with_booked: Set of day numbers that have any booked slots
    
    Returns:
        InlineKeyboardMarkup with calendar grid
    """
    kb = InlineKeyboardBuilder()
    
    # Header: month name + year
    kb.button(text=f"📅 {MONTHS_RU[month]} {year}", callback_data="cal_ignore")
    kb.adjust(1)
    
    # Weekday headers (non-clickable)
    for day_name in WEEKDAYS_SHORT:
        kb.button(text=day_name, callback_data="cal_ignore")
    
    # Get calendar data
    cal = calendar.Calendar(firstweekday=0)  # Monday first
    today = datetime.now()
    
    month_days = cal.monthdayscalendar(year, month)
    
    for week in month_days:
        for day in week:
            if day == 0:
                # Empty cell
                kb.button(text=" ", callback_data="cal_ignore")
            else:
                # Format date as DD.MM for callback
                date_str = f"{day:02d}.{month:02d}"
                
                is_today = (year == today.year and month == today.month and day == today.day)
                has_free = day in days_with_free
                has_booked = day in days_with_booked
                
                # Choose display style
                if is_today:
                    if has_free:
                        label = f"📍{day}"
                    else:
                        label = f"📍{day}"
                elif has_free and has_booked:
                    # Mix: some free, some booked
                    label = f"🟢{day}"
                elif has_free:
                    # Only free slots
                    label = f"🟢{day}"
                elif has_booked:
                    # All booked, no free
                    label = f"🔵{day}"
                else:
                    # No slots at all
                    label = f"{day}"
                
                kb.button(text=label, callback_data=f"cal_day_{date_str}")
    
    # Navigation row
    # Previous month
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1
    
    # Next month
    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1
    
    kb.button(text="◀️", callback_data=f"cal_prev_{prev_year}-{prev_month:02d}")
    kb.button(text="📋 Список", callback_data="schedule_list_view")
    kb.button(text="▶️", callback_data=f"cal_next_{next_year}-{next_month:02d}")
    
    # Layout: 1 (header) + 7 (weekdays) + weeks*7 + 3 (navigation)
    sizes = [1, 7]  # header + weekday names
    for week in month_days:
        sizes.append(7)
    sizes.append(3)  # navigation
    
    kb.adjust(*sizes)
    return kb.as_markup()
