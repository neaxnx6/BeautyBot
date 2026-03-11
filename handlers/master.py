from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.db_cmds import register_master, get_master_by_tg_id, add_slot, get_master_slots_with_ids, get_master_id_by_tg_id, delete_slot_db
from keyboards.master import master_panel_kb, cancel_kb
from keyboards.basic import main_menu_kb
from config import ADMIN_ID
from datetime import datetime, timedelta
from typing import Optional

router = Router()

# Russian weekday names
WEEKDAYS_FULL = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
WEEKDAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

class MasterStates(StatesGroup):
    waiting_for_slot_time = State()
    selecting_date = State()
    selecting_time = State()

def parse_slot_datetime(slot_str: str) -> Optional[datetime]:
    """Parse slot datetime string like '05.02 14:00' to datetime object."""
    try:
        current_year = datetime.now().year
        dt = datetime.strptime(f"{slot_str} {current_year}", "%d.%m %H:%M %Y")
        return dt
    except:
        return None

def is_slot_in_past(slot_str: str) -> bool:
    """Check if slot datetime is in the past."""
    dt = parse_slot_datetime(slot_str)
    if dt is None:
        return False
    return dt < datetime.now()

def format_slot_with_weekday(slot_str: str) -> str:
    """Add weekday to slot string: '05.02 14:00' -> 'Ср 05.02 14:00'"""
    dt = parse_slot_datetime(slot_str)
    if dt is None:
        return slot_str
    return f"{WEEKDAYS_FULL[dt.weekday()]} {slot_str}"

def pluralize_slots(count: int) -> str:
    """Правильное склонение слова 'окошко': 1 окошко, 2-4 окошка, 5+ окошек"""
    if count % 10 == 1 and count % 100 != 11:
        return f"{count} окошко"
    elif 2 <= count % 10 <= 4 and (count % 100 < 10 or count % 100 >= 20):
        return f"{count} окошка"
    else:
        return f"{count} окошек"

# --- Entry Point ---
@router.message(F.text == "⚙️ Панель Мастера")
async def open_master_panel(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID) and not await get_master_by_tg_id(message.from_user.id):
        await message.answer("У вас нет доступа.")
        return

    master = await get_master_by_tg_id(message.from_user.id)
    if not master:
        await register_master(message.from_user.id, message.from_user.full_name)
        await message.answer("🆕 Профиль мастера создан!")

    # Removed formal greeting, just show the keyboard
    await message.answer("👩‍🎨 Панель мастера:", reply_markup=master_panel_kb())
    
    from keyboards.calendar import build_month_calendar
    now = datetime.now()
    days_free, days_booked = await build_calendar_data(message.from_user.id, now.year, now.month)
    markup = build_month_calendar(now.year, now.month, days_free, days_booked)
    await message.answer("📅 *Ваше расписание*\n🟢 свободные  🔴 все заняты  📍 сегодня", reply_markup=markup)

@router.message(F.text == "🏠 Главное меню")
async def back_to_main(message: types.Message):
    await message.answer("Главное меню", reply_markup=main_menu_kb(is_master=True))

# --- Get Invite Link ---
@router.message(F.text == "🔗 Моя Ссылка")
async def get_my_link(message: types.Message, bot: Bot):
    master_db_id = await get_master_id_by_tg_id(message.from_user.id)
    if not master_db_id:
        await message.answer("Ошибка: Профиль не найден.")
        return
        
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    link = f"https://t.me/{bot_username}?start=master_{master_db_id}"
    
    await message.answer(
        f"🔗 *Ваша персональная ссылка:*\n`{link}`\n\n"
        "Отправьте её клиентам.",
        disable_web_page_preview=True
    )

# --- Add Slot Flow (Integrated with Calendar) ---
@router.callback_query(F.data.startswith("addslot_"))
async def process_addslot_calendar(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    full_date_str = parts[1]  # "YYYY-MM-DD"
    year_month = parts[2] if len(parts) > 2 else f"{datetime.now().year}-{datetime.now().month:02d}"
    
    await state.update_data(selected_date=full_date_str, return_ym=year_month)
    
    kb = InlineKeyboardBuilder()
    now = datetime.now()
    selected_date = datetime.strptime(full_date_str, "%Y-%m-%d").date()
    is_today = selected_date == now.date()
    
    # Получаем уже существующие слоты на эту дату
    existing_slots = await get_master_slots_with_ids(callback.from_user.id)
    date_formatted = selected_date.strftime('%d.%m')
    existing_times = set()
    for slot in existing_slots:
        slot_datetime = slot[1]  # "DD.MM HH:MM"
        if slot_datetime.startswith(date_formatted):
            existing_times.add(slot_datetime.split()[1])  # "HH:MM"
    
    for hour in range(9, 21):
        for minute in [0, 30]:
            if hour == 20 and minute == 30: continue
            if is_today:
                slot_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if slot_time <= now: continue
            
            time_str = f"{hour:02d}:{minute:02d}"
            if time_str in existing_times:
                kb.button(text=f"✅ {time_str}", callback_data=f"time_added_{time_str}")
            else:
                kb.button(text=time_str, callback_data=f"time_{time_str}")
    
    date_str_short = selected_date.strftime('%d.%m')
    kb.button(text="⬅️ Назад", callback_data=f"cal_day_{date_str_short}_{year_month}")
    kb.adjust(4)
    
    weekday = WEEKDAYS_FULL[selected_date.weekday()]
    display_date = f"{weekday} {date_formatted}"
    
    await callback.message.edit_text(f"🕐 Выберите время на *{display_date}*:", reply_markup=kb.as_markup())
    await state.set_state(MasterStates.selecting_time)
    await callback.answer()

@router.callback_query(F.data.startswith("time_"))
async def process_time_selection(callback: types.CallbackQuery, state: FSMContext):
    if callback.data.startswith("time_added_"):
        await callback.answer("Это время уже добавлено!", show_alert=True)
        return

    time_str = callback.data.split("_")[1]
    data = await state.get_data()
    date_str = data.get("selected_date")
    year_month = data.get("return_ym", f"{datetime.now().year}-{datetime.now().month:02d}")
    
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    full_datetime = f"{date_obj.strftime('%d.%m')} {time_str}"
    
    result = await add_slot(callback.fromuser.id if hasattr(callback, "fromuser") else callback.from_user.id, full_datetime)
    
    if result == True:
        await callback.answer(f"Окошко {time_str} добавлено!", show_alert=False)
        
        # Обновляем текущую инлайн-клавиатуру напрямую для моментального визуального отклика
        markup = callback.message.reply_markup
        if markup:
            kb_new = InlineKeyboardBuilder()
            
            # Перестраиваем клавиатуру, заменяя текст и callback_data нужной кнопки
            for row in markup.inline_keyboard:
                for btn in row:
                    if btn.callback_data == f"time_{time_str}":
                        kb_new.button(text=f"✅ {time_str}", callback_data=f"time_added_{time_str}")
                    else:
                        kb_new.button(text=btn.text, callback_data=btn.callback_data)
            
            # В меню выбора времени у нас по 4 кнопки в ряд
            kb_new.adjust(4)
            
            try:
                await callback.message.edit_reply_markup(reply_markup=kb_new.as_markup())
            except Exception as e:
                import logging
                logging.error(f"Failed to update time inline keyboard: {e}")
    elif result == "duplicate":
        await callback.answer(f"❌ Такое окошко уже существует!", show_alert=True)
    else:
        await callback.answer("❌ Ошибка: Профиль мастера не найден.", show_alert=True)

@router.callback_query(F.data == "manual_slot")
async def manual_slot_entry(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📝 Введите дату и время вручную.\n"
        "Формат: `05.02 14:00`\n\n"
        "Или напишите `отмена` для выхода."
    )
    await state.set_state(MasterStates.waiting_for_slot_time)
    await callback.answer()

@router.callback_query(F.data == "cancel_slot")
async def cancel_slot_creation(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Отменено.")
    await callback.answer()

@router.message(MasterStates.waiting_for_slot_time)
async def process_manual_slot_time(message: types.Message, state: FSMContext):
    if message.text.lower() in ["отмена", "❌ отмена"]:
        await state.clear()
        await message.answer("Отменено.", reply_markup=master_panel_kb())
        return

    time_str = message.text
    
    if is_slot_in_past(time_str):
        await message.answer("❌ Нельзя создать окошко в прошлом!", reply_markup=master_panel_kb())
        await state.clear()
        return
    
    result = await add_slot(message.from_user.id, time_str)
    
    if result == True:
        await message.answer(f"✅ Окошко `{time_str}` добавлено!", reply_markup=master_panel_kb())
    elif result == "duplicate":
        await message.answer(f"❌ Такое окошко уже существует!", reply_markup=master_panel_kb())
    else:
        await message.answer("Ошибка: Профиль мастера не найден.", reply_markup=master_panel_kb())
    
    await state.clear()

# --- View/Manage Schedule ---
async def build_schedule_message(user_id: int):
    """Build schedule overview - level 1: grouped by days"""
    from datetime import datetime
    from collections import defaultdict
    
    slots = await get_master_slots_with_ids(user_id)
    
    # Filter out past slots and group by date
    slots_by_date = defaultdict(list)
    for row in slots:
        time_str = row[1]  # datetime is second field
        if not is_slot_in_past(time_str):
            # Extract date part (DD.MM)
            date_part = time_str.split()[0]  # "DD.MM"
            slots_by_date[date_part].append(row)
    
    if not slots_by_date:
        return "📅 Расписание пусто.", None
    
    kb = InlineKeyboardBuilder()
    text = "📅 *Ваше Расписание*\n_Нажмите на день для деталей_\n\n"
    
    # Create buttons for each day with counters
    for date_str in sorted(slots_by_date.keys(), key=lambda d: parse_date_for_sort(d)):
        day_slots = slots_by_date[date_str]
        total = len(day_slots)
        booked = sum(1 for row in day_slots if row[2] == 1)
        
        # Format: "Пн 05.02 (2/4)" - booked/total
        weekday = get_weekday_for_date(date_str)
        kb.button(text=f"{weekday} {date_str} ({booked}/{total})", callback_data=f"schedule_day_{date_str}")
    
    kb.adjust(2)  # 2 days per row
    kb.row(types.InlineKeyboardButton(text="📅 К календарю", callback_data="back_to_schedule_overview"))
    return text, kb.as_markup()

def parse_date_for_sort(date_str: str):
    """Parse DD.MM to sortable format"""
    try:
        from datetime import datetime
        day, month = map(int, date_str.split('.'))
        # Assume current year
        year = datetime.now().year
        return datetime(year, month, day)
    except:
        return datetime.now()

def get_weekday_for_date(date_str: str):
    """Get weekday name for DD.MM date"""
    try:
        from datetime import datetime
        day, month = map(int, date_str.split('.'))
        year = datetime.now().year
        dt = datetime(year, month, day)
        return WEEKDAYS_SHORT[dt.weekday()]
    except:
        return ""

async def build_calendar_data(user_id: int, year: int, month: int):
    """Get sets of days with free/booked slots for a given month"""
    from collections import defaultdict
    
    slots = await get_master_slots_with_ids(user_id)
    
    days_with_free = set()
    days_with_booked = set()
    
    for row in slots:
        time_str = row[1]  # "DD.MM HH:MM"
        is_booked = row[2]
        
        if is_slot_in_past(time_str):
            continue
        
        try:
            date_part = time_str.split()[0]  # "DD.MM"
            day, mon = map(int, date_part.split('.'))
            if mon == month:
                if is_booked == 1:
                    days_with_booked.add(day)
                else:
                    days_with_free.add(day)
        except:
            continue
    
    return days_with_free, days_with_booked

@router.message(F.text == "📅 Расписание")
async def view_schedule(message: types.Message):
    from keyboards.calendar import build_month_calendar
    now = datetime.now()
    days_free, days_booked = await build_calendar_data(message.from_user.id, now.year, now.month)
    markup = build_month_calendar(now.year, now.month, days_free, days_booked)
    await message.answer("📅 *Ваше расписание*\n🟢 свободные  🔴 все заняты  📍 сегодня", reply_markup=markup)

@router.callback_query(F.data == "cal_ignore")
async def calendar_ignore(callback: types.CallbackQuery):
    await callback.answer()

@router.callback_query(F.data == "cal_past")
async def calendar_past(callback: types.CallbackQuery):
    await callback.answer("Этот день уже прошёл.", show_alert=True)

@router.callback_query(F.data.startswith("cal_prev_"))
async def calendar_prev_month(callback: types.CallbackQuery):
    from keyboards.calendar import build_month_calendar
    parts = callback.data.split("_")[2]  # "YYYY-MM"
    year, month = map(int, parts.split("-"))
    days_free, days_booked = await build_calendar_data(callback.from_user.id, year, month)
    markup = build_month_calendar(year, month, days_free, days_booked)
    await callback.message.edit_text("📅 *Ваше расписание*\n🟢 свободные  🔴 все заняты  📍 сегодня", reply_markup=markup)
    await callback.answer()

@router.callback_query(F.data.startswith("cal_next_"))
async def calendar_next_month(callback: types.CallbackQuery):
    from keyboards.calendar import build_month_calendar
    parts = callback.data.split("_")[2]  # "YYYY-MM"
    year, month = map(int, parts.split("-"))
    days_free, days_booked = await build_calendar_data(callback.from_user.id, year, month)
    markup = build_month_calendar(year, month, days_free, days_booked)
    await callback.message.edit_text("📅 *Ваше расписание*\n🟢 свободные  🔴 все заняты  📍 сегодня", reply_markup=markup)
    await callback.answer()

@router.callback_query(F.data.startswith("cal_day_"))
async def calendar_day_click(callback: types.CallbackQuery, state: FSMContext):
    """Calendar day clicked - show day schedule"""
    parts = callback.data.split("_")
    date_str = parts[2]  # "DD.MM"
    year_month = parts[3] if len(parts) > 3 else f"{datetime.now().year}-{datetime.now().month:02d}"
    
    slots = await get_master_slots_with_ids(callback.from_user.id)
    
    slots_for_day = []
    for row in slots:
        time_str = row[1]
        if not is_slot_in_past(time_str):
            if time_str.split()[0] == date_str:
                slots_for_day.append(row)
    
    day, current_month = date_str.split(".")
    year = year_month.split("-")[0]
    full_date_str = f"{year}-{current_month}-{day}"
    
    if not slots_for_day:
        kb = InlineKeyboardBuilder()
        kb.button(text="🕒 Добавить время", callback_data=f"addslot_{full_date_str}_{year_month}")
        kb.button(text="⬅️ К календарю", callback_data=f"back_to_calendar_{year_month}")
        kb.adjust(1)
        
        text = f"📅 *{get_weekday_for_date(date_str)} {date_str}*\n\nНа этот день нет окошек. Хотите добавить?"
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
        await callback.answer()
        return
    
    kb = InlineKeyboardBuilder()
    slots_for_day.sort(key=lambda x: datetime.strptime(x[1], "%d.%m %H:%M"))
    
    text = f"📅 *{get_weekday_for_date(date_str)} {date_str}*\n_(Нажмите на слот для деталей)_\n\n"
    
    for row in slots_for_day:
        slot_id, time_str, is_booked = row[0], row[1], row[2]
        time_only = time_str.split()[1] if ' ' in time_str else time_str
        status_text = "свободно" if is_booked == 0 else "занято"
        emoji = "✅" if is_booked == 0 else "🔴"
        kb.button(text=f"{emoji} {time_only} — {status_text}", callback_data=f"view_slot_{slot_id}")
    
    kb.button(text="🕒 Добавить время", callback_data=f"addslot_{full_date_str}_{year_month}")
    kb.button(text=f"🗑 Удалить день ({pluralize_slots(len(slots_for_day))})", callback_data=f"clear_day_{date_str}")
    kb.button(text="⬅️ К календарю", callback_data=f"back_to_calendar_{year_month}")
    kb.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("schedule_day_"))
async def view_day_schedule(callback: types.CallbackQuery, state: FSMContext):
    """Legacy: redirect to calendar day view"""
    date_str = callback.data.split("_")[2]
    callback.data = f"cal_day_{date_str}"
    await calendar_day_click(callback, state)

@router.callback_query(F.data == "schedule_list_view")
async def schedule_list_view(callback: types.CallbackQuery):
    """Show old list view"""
    text, markup = await build_schedule_message(callback.from_user.id)
    if markup:
        await callback.message.edit_text(text, reply_markup=markup)
    else:
        await callback.message.edit_text("📅 Расписание пусто.")
    await callback.answer()

@router.callback_query(F.data.startswith("back_to_calendar"))
@router.callback_query(F.data == "back_to_schedule_overview")
async def back_to_schedule_overview(callback: types.CallbackQuery):
    """Return to calendar view"""
    from keyboards.calendar import build_month_calendar
    now = datetime.now()
    year, month = now.year, now.month
    
    if "_" in callback.data and callback.data.startswith("back_to_calendar_"):
        parts = callback.data.split("_")
        if len(parts) >= 4:
            try:
                year, month = map(int, parts[3].split("-"))
            except ValueError:
                pass
                
    days_free, days_booked = await build_calendar_data(callback.from_user.id, year, month)
    markup = build_month_calendar(year, month, days_free, days_booked)
    await callback.message.edit_text("📅 *Ваше расписание*\n🟢 свободные  🔴 все заняты  📍 сегодня", reply_markup=markup)
    await callback.answer()

@router.callback_query(F.data.startswith("clear_day_"))
async def clear_day_confirm(callback: types.CallbackQuery):
    """Handle clear day request - ask for confirmation if has booked slots"""
    from datetime import datetime
    
    date_str = callback.data.split("_")[2]  # "DD.MM"
    
    # Get slots for this day
    slots = await get_master_slots_with_ids(callback.from_user.id)
    slots_for_day = []
    for row in slots:
        time_str = row[1]
        if not is_slot_in_past(time_str):
            if time_str.split()[0] == date_str:
                slots_for_day.append(row)
    
    if not slots_for_day:
        await callback.answer("Нет окошек для удаления", show_alert=True)
        return
    
    # Check if any slots are booked
    booked_slots = [row for row in slots_for_day if row[2] == 1]
    
    if booked_slots:
        # Need confirmation
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Да, очистить", callback_data=f"confirm_clear_day_{date_str}")
        kb.button(text="❌ Отмена", callback_data=f"schedule_day_{date_str}")
        kb.adjust(1)
        
        text = f"⚠️ *Подтверждение*\n\n"
        text += f"Вы уверены, что хотите удалить {pluralize_slots(len(slots_for_day))}?\n\n"
        text += f"🔴 Занято: {pluralize_slots(len(booked_slots))}\n"
        text += f"✅ Свободно: {pluralize_slots(len(slots_for_day) - len(booked_slots))}\n\n"
        text += "Клиентам будут отправлены уведомления об отмене."
        
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
        await callback.answer()
    else:
        # No booked slots - delete immediately without confirmation
        await confirm_clear_day(callback, bot=callback.bot)

@router.callback_query(F.data.startswith("confirm_clear_day_"))
async def confirm_clear_day(callback: types.CallbackQuery, bot: Bot = None):
    """Actually clear all slots for the day"""
    from database.db_cmds import delete_slot_db, get_slot_info
    
    # Handle both "clear_day_DD.MM" (direct call) and "confirm_clear_day_DD.MM" (button click)
    parts = callback.data.split("_")
    date_str = parts[3] if parts[0] == "confirm" else parts[2]
    
    # Get slots for this day
    slots = await get_master_slots_with_ids(callback.from_user.id)
    slots_for_day = []
    for row in slots:
        time_str = row[1]
        if not is_slot_in_past(time_str):
            if time_str.split()[0] == date_str:
                slots_for_day.append(row)
    
    deleted_count = 0
    notified_clients = []
    
    for row in slots_for_day:
        slot_id, time_str, is_booked, client_id = row[0], row[1], row[2], row[3]
        
        # Delete slot
        await delete_slot_db(slot_id)
        deleted_count += 1
        
        # Notify client if booked
        if is_booked and client_id and bot:
            try:
                await bot.send_message(
                    client_id,
                    f"⚠️ Ваша запись отменена мастером\n\n"
                    f"📅 {format_slot_with_weekday(time_str)}\n\n"
                    f"Приносим извинения за неудобства."
                )
                notified_clients.append(client_id)
            except:
                pass
    
    # Return to calendar view
    from keyboards.calendar import build_month_calendar
    now = datetime.now()
    year, month = now.year, now.month
    
    parts = date_str.split(".")
    if len(parts) == 2:
        month = int(parts[1])
    
    days_free, days_booked = await build_calendar_data(callback.from_user.id, year, month)
    markup = build_month_calendar(year, month, days_free, days_booked)
    
    await callback.message.edit_text(
        f"✅ День очищен! Удалено: {pluralize_slots(deleted_count)}\n"
        f"📩 Уведомлено клиентов: {len(set(notified_clients))}\n\n"
        "📅 *Ваше расписание*\n🟢 свободные  🔴 все заняты  📍 сегодня",
        reply_markup=markup
    )
    
    await callback.answer("День очищен!")

@router.callback_query(F.data.startswith("view_slot_"))
async def view_slot_details(callback: types.CallbackQuery, bot: Bot):
    """Show slot details with action buttons"""
    slot_id = int(callback.data.split("_")[-1])
    
    # Get all slots to find this one
    slots = await get_master_slots_with_ids(callback.from_user.id)
    slot_data = None
    for row in slots:
        if row[0] == slot_id:
            slot_data = row
            break
    
    if not slot_data:
        await callback.answer("Слот не найден.")
        return
    
    # Unpack: slot_id, datetime, is_booked, client_id, client_name, client_username, service_name, service_price, service_category, service_subcategory
    slot_id, datetime_str, is_booked, client_id, client_name, client_username, svc_name, svc_price, svc_cat, svc_subcat = slot_data
    
    formatted_time = format_slot_with_weekday(datetime_str)
    
    if is_booked:
        # Build client link
        if client_username:
            client_link = f"@{client_username}"
        elif client_name:
            client_link = f"[{client_name}](tg://user?id={client_id})"
        else:
            client_link = "Клиент"
        
        # Build full service name
        if svc_name:
            cat_clean = svc_cat.split(' ', 1)[1] if svc_cat and ' ' in svc_cat else (svc_cat or "")
            if svc_subcat:
                full_svc = f"{cat_clean} ({svc_subcat}) • {svc_name}"
            else:
                full_svc = f"{cat_clean} • {svc_name}" if cat_clean else svc_name
        else:
            full_svc = "Не указана"
        
        msg = f"📋 *Детали записи*\n\n"
        msg += f"📅 *Дата и время:* {formatted_time}\n"
        msg += f"👤 *Клиент:* {client_link}\n"
        msg += f"💅 *Услуга:* {full_svc}\n"
        if svc_price:
            msg += f"💰 *Стоимость:* {int(svc_price)}₽\n"
        
        kb = InlineKeyboardBuilder()
        kb.button(text="❌ Отменить запись", callback_data=f"cancel_client_booking_{slot_id}")
        kb.button(text="🗑 Удалить окошко", callback_data=f"force_delete_slot_{slot_id}")
        kb.button(text="⬅️ Назад", callback_data="back_to_schedule")
        kb.adjust(1)
    else:
        # Free slot
        msg = f"📋 *Свободное окошко*\n\n📅 *Дата и время:* {formatted_time}\n\nЭто окошко пока никем не занято."
        
        kb = InlineKeyboardBuilder()
        kb.button(text="🗑 Удалить окошко", callback_data=f"force_delete_slot_{slot_id}")
        kb.button(text="⬅️ Назад", callback_data="back_to_schedule")
        kb.adjust(1)
    
    await callback.message.edit_text(msg, reply_markup=kb.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("cancel_client_booking_"))
async def cancel_client_booking(callback: types.CallbackQuery, bot: Bot):
    """Cancel booking but keep the slot"""
    slot_id = int(callback.data.split("_")[-1])
    
    # Get slot info before canceling
    slots = await get_master_slots_with_ids(callback.from_user.id)
    slot_data = None
    for row in slots:
        if row[0] == slot_id:
            slot_data = row
            break
    
    if not slot_data:
        await callback.answer("Ошибка: слот не найден.")
        return
    
    slot_id, datetime_str, is_booked, client_id, client_name, client_username, svc_name, svc_price, svc_cat, svc_subcat = slot_data
    
    # Cancel booking (using existing function, but need to create one for master)
    from database.db_cmds import cancel_booking_db
    success = await cancel_booking_db(slot_id, client_id)
    
    if success:
        # Notify client
        formatted_time = format_slot_with_weekday(datetime_str)
        try:
            await bot.send_message(
                chat_id=client_id,
                text=f"⚠️ *Ваша запись отменена мастером*\n\n📅 {formatted_time}\n\nПриносим извинения за неудобства."
            )
        except: pass
        
        # Return to schedule
        date_str_short = datetime_str.split()[0]
        year_month = f"{datetime.now().year}-{datetime.now().month:02d}"
        callback.data = f"cal_day_{date_str_short}_{year_month}"
        await calendar_day_click(callback, state)
    else:
        await callback.answer("Ошибка отмены.")
    
    await callback.answer()

@router.callback_query(F.data.startswith("force_delete_slot_"))
async def force_delete_slot(callback: types.CallbackQuery, bot: Bot):
    """Delete slot entirely (with or without booking)"""
    slot_id = int(callback.data.split("_")[-1])
    
    # Get slot info to notify client if booked
    slots = await get_master_slots_with_ids(callback.from_user.id)
    slot_data = None
    for row in slots:
        if row[0] == slot_id:
            slot_data = row
            break
    
    if slot_data:
        slot_id, datetime_str, is_booked, client_id, client_name, client_username, svc_name, svc_price, svc_cat, svc_subcat = slot_data
        
        # If booked, notify client
        if is_booked and client_id:
            formatted_time = format_slot_with_weekday(datetime_str)
            try:
                await bot.send_message(
                    chat_id=client_id,
                    text=f"⚠️ *Ваша запись отменена мастером*\n\n📅 {formatted_time}\n\nПриносим извинения за неудобства."
                )
            except: pass
    
    success = await delete_slot_db(slot_id)
    if success:
        date_str_short = datetime_str.split()[0] if slot_data else datetime.now().strftime('%d.%m')
        year_month = f"{datetime.now().year}-{datetime.now().month:02d}"
        callback.data = f"cal_day_{date_str_short}_{year_month}"
        await calendar_day_click(callback, state=None)
    else:
        await callback.answer("Ошибка удаления.")
    
    await callback.answer()

@router.callback_query(F.data == "back_to_schedule")
async def back_to_schedule(callback: types.CallbackQuery):
    """Return to schedule view"""
    await back_to_schedule_overview(callback)
