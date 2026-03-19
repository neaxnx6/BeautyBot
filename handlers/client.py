from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.db_cmds import (
    get_all_masters, get_available_slots, book_slot, get_slot_info, 
    add_user, get_client_bookings, cancel_booking_db, get_user_master, 
    get_master_name_by_id, get_service_categories, get_services_in_category,
    get_service_info, get_subcategories, get_master_by_tg_id, get_master_id_by_tg_id,
    get_master_tg_id_by_slot_id
)
from config import ADMIN_ID

router = Router()

class BookingStates(StatesGroup):
    selecting_master = State()
    confirming_booking = State()
    selecting_category = State()
    selecting_subcategory = State()
    selecting_service = State()
    selecting_day = State()  # NEW: First select day
    selecting_slot = State() # Then select specific time

# --- 1. Start Booking ---
@router.message(F.text == "💅 Записаться")
async def start_booking(message: types.Message, state: FSMContext):
    await add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    
    # Check booking limit FIRST (before any selections)
    client_bookings = await get_client_bookings(message.from_user.id)
    
    if len(client_bookings) >= 3:
        # Show current bookings with cancel options
        text = "⚠️ *Достигнут лимит записей*\n\n"
        text += f"У вас уже **{len(client_bookings)} активных записи**.\n"
        text += "Отмените одну через \"📝 Мои Записи\", чтобы забронировать новую."
        
        await message.answer(text)
        return
    
    # If the user IS a master themselves, auto-link them to their own profile
    master_self = await get_master_by_tg_id(message.from_user.id)
    if master_self:
        own_master_id = master_self[0]
        await state.update_data(master_id=own_master_id)
        master_name = await get_master_name_by_id(own_master_id)
        await state.update_data(master_name=master_name)
        await show_categories(message, own_master_id, state)
        return

    linked_master_id = await get_user_master(message.from_user.id)
    
    if linked_master_id:
        await state.update_data(master_id=linked_master_id)
        master_name = await get_master_name_by_id(linked_master_id)
        await state.update_data(master_name=master_name)
        await show_categories(message, linked_master_id, state)
        return

    masters = await get_all_masters()
    
    if not masters:
        await message.answer("Пока нет доступных мастеров 😔")
        return

    if len(masters) == 1:
        master_id, master_name = masters[0]
        await state.update_data(master_id=master_id, master_name=master_name)
        await show_categories(message, master_id, state)
    else:
        kb = InlineKeyboardBuilder()
        for m_id, m_name in masters:
            kb.button(text=m_name, callback_data=f"sel_master_{m_id}")
        await message.answer("Выберите мастера:", reply_markup=kb.as_markup())
        await state.set_state(BookingStates.selecting_master)

@router.callback_query(F.data.startswith("sel_master_"))
async def process_master_selection(callback: types.CallbackQuery, state: FSMContext):
    master_id = int(callback.data.split("_")[-1])
    await state.update_data(master_id=master_id)
    master_name = await get_master_name_by_id(master_id)
    await state.update_data(master_name=master_name)
    
    await show_categories(callback.message, master_id, state, edit_message=True)

# --- 2. Select Category ---
async def show_categories(message: types.Message, master_id: int, state: FSMContext, edit_message=False):
    categories = await get_service_categories(master_id)
    
    if not categories:
        await message.answer("У мастера пока нет списка услуг 🥺")
        return

    kb = InlineKeyboardBuilder()
    for cat in categories:
        kb.button(text=cat, callback_data=f"sel_cat_{cat}")
    
    kb.button(text="❌ Отмена", callback_data="cancel_booking")
    kb.adjust(1)
    
    text = "✨ Выберите категорию услуг:"
    if edit_message:
        await message.edit_text(text, reply_markup=kb.as_markup())
    else:
        await message.answer(text, reply_markup=kb.as_markup())
    
    await state.set_state(BookingStates.selecting_category)

@router.callback_query(F.data.startswith("sel_cat_"))
async def process_category(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.split("sel_cat_")[1]
    await state.update_data(category=category)
    data = await state.get_data()
    master_id = data.get("master_id")
    
    # Check if category has subcategories
    subcategories = await get_subcategories(master_id, category)
    
    if subcategories:
        # Clear old subcategory before showing new ones
        await state.update_data(subcategory=None)
        # Show subcategories (e.g. for Маникюр: Короткие, Средние, Длинные)
        await show_subcategories(callback.message, master_id, category, subcategories, state)
    else:
        # Clear subcategory for categories without subcategories
        await state.update_data(subcategory=None)
        # Go directly to services (e.g. for Комплекс, Педикюр)
        await show_services(callback.message, master_id, category, None, state, edit_message=True)
    
    await callback.answer()

# --- 3. Select Subcategory (if applicable) ---
async def show_subcategories(message: types.Message, master_id: int, category: str, subcategories: list, state: FSMContext):
    kb = InlineKeyboardBuilder()
    
    for subcat in subcategories:
        kb.button(text=subcat, callback_data=f"sel_subcat_{subcat}")
    
    kb.button(text="⬅️ Назад", callback_data="back_to_cats")
    kb.adjust(1)
    
    # Remove emoji from category for cleaner display
    cat_clean = category.split(' ', 1)[1] if ' ' in category else category
    await message.edit_text(f"💅 {cat_clean} — выберите длину:", reply_markup=kb.as_markup())
    await state.set_state(BookingStates.selecting_subcategory)

@router.callback_query(F.data.startswith("sel_subcat_"))
async def process_subcategory(callback: types.CallbackQuery, state: FSMContext):
    subcategory = callback.data.split("sel_subcat_")[1]
    await state.update_data(subcategory=subcategory)
    
    data = await state.get_data()
    master_id = data.get("master_id")
    category = data.get("category")
    
    await show_services(callback.message, master_id, category, subcategory, state, edit_message=True)
    await callback.answer()

# --- 4. Select Service ---
async def show_services(message: types.Message, master_id: int, category: str, subcategory: str, state: FSMContext, edit_message=False):
    services = await get_services_in_category(master_id, category, subcategory)
    
    kb = InlineKeyboardBuilder()
    for s_id, s_name, s_price, s_dur, s_desc, s_subcat in services:
        label = f"{s_name} — {int(s_price)}₽"
        kb.button(text=label, callback_data=f"sel_svc_{s_id}")
    
    kb.button(text="⬅️ Назад", callback_data="back_from_services")
    kb.adjust(1)
    
    # Build title
    cat_clean = category.split(' ', 1)[1] if ' ' in category else category
    if subcategory:
        title = f"💅 {cat_clean} ({subcategory}) — выберите услугу:"
    else:
        title = f"💅 {cat_clean} — выберите услугу:"
    
    if edit_message:
        await message.edit_text(title, reply_markup=kb.as_markup())
    else:
        await message.answer(title, reply_markup=kb.as_markup())
    
    await state.set_state(BookingStates.selecting_service)

@router.callback_query(F.data == "back_from_services")
async def back_from_services(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    master_id = data.get("master_id")
    category = data.get("category")
    
    # Check if current category actually has subcategories
    subcategories = await get_subcategories(master_id, category)
    
    if subcategories:
        # Go back to subcategory selector
        await show_subcategories(callback.message, master_id, category, subcategories, state)
    else:
        # Go back to categories (no subcategories exist)
        await show_categories(callback.message, master_id, state, edit_message=True)
    
    await callback.answer()

@router.callback_query(F.data.startswith("sel_svc_"))
async def process_service(callback: types.CallbackQuery, state: FSMContext):
    service_id = int(callback.data.split("_")[-1])
    await state.update_data(service_id=service_id)
    
    await show_slots_logic(callback.message, state=state, edit_message=True)
    await callback.answer()

# --- 5. Show Days (Level 1) ---
async def show_slots_logic(message: types.Message, state: FSMContext, edit_message=False, year: int = None, month: int = None):
    """Уровень 1: Показ доступных дней в виде календаря"""
    from datetime import datetime
    from collections import defaultdict
    from handlers.master import get_weekday_for_date, parse_date_for_sort
    
    data = await state.get_data()
    master_id = data.get("master_id")
    service_id = data.get("service_id")
    
    # Получаем длительность выбранной услуги
    svc_duration = 30
    if service_id:
        svc_info = await get_service_info(service_id)
        if svc_info and svc_info[2]:
            svc_duration = svc_info[2]
    
    slots = await get_available_slots(master_id, svc_duration)
    
    if not slots:
        text = "Пока нет свободных окошек 🥺\nПопробуйте позже!"
        if edit_message:
            await message.edit_text(text)
        else:
            await message.answer(text)
        return
    
    # Calculate Current Year and Month
    now = datetime.now()
    if not year or not month:
        # Default to first available month with slots, or current month
        year, month = now.year, now.month
        
        # Simple optimization: if no slots in current month, try next months
        # (This is basic, assumes slots are sorted and exist)
        if slots:
            first_slot_date = slots[0][1].split()[0] # "DD.MM"
            s_day, s_month = map(int, first_slot_date.split('.'))
            target_date = datetime(now.year, s_month, s_day)
            # If the slot is earlier in the year than current month, it's next year (e.g. now=Dec, slot=Jan)
            if target_date < now and s_month < now.month:
                year = now.year + 1
            month = s_month
    
    # Filter slots for the selected month and collect free days
    days_with_free = set()
    for s_id, s_time in slots:
        date_part = s_time.split()[0]  # "DD.MM"
        d, m = map(int, date_part.split('.'))
        
        # Determine slot year (heuristic: if month < now.month, it's next year)
        slot_year = now.year
        if m < now.month:
            slot_year += 1
            
        if slot_year == year and m == month:
            days_with_free.add(d)
    
    # Get service info for title
    svc_info = await get_service_info(service_id)
    svc_name, svc_price, svc_dur, svc_desc, svc_cat, svc_subcat = svc_info
    
    # Build full service title
    cat_clean = svc_cat.split(' ', 1)[1] if ' ' in svc_cat else svc_cat
    if svc_subcat:
        full_title = f"{cat_clean} ({svc_subcat}) • {svc_name}"
    else:
        full_title = f"{cat_clean} • {svc_name}"
    
    # Build message
    title = f"✅ *{full_title}* — {int(svc_price)}₽\n\n"
    if svc_desc:
        title += f"Включено: {svc_desc}\n\n"
    title += "📅 Выберите подходящий день:"
    
    from keyboards.calendar import build_client_month_calendar
    kb = build_client_month_calendar(year, month, days_with_free)
    
    if edit_message:
        await message.edit_text(title, reply_markup=kb)
    else:
        await message.answer(title, reply_markup=kb)
        
    await state.set_state(BookingStates.selecting_day)

@router.callback_query(F.data.startswith("client_cal_prev_") | F.data.startswith("client_cal_next_"))
async def process_client_calendar_nav(callback: types.CallbackQuery, state: FSMContext):
    action = callback.data.split("_")[2] # "prev" or "next"
    year_month = callback.data.split("_")[3]
    year, month = map(int, year_month.split("-"))
    
    await show_slots_logic(callback.message, state=state, edit_message=True, year=year, month=month)
    await callback.answer()

@router.callback_query(F.data == "cal_ignore")
async def process_client_calendar_ignore(callback: types.CallbackQuery):
    await callback.answer("⏳ Недоступно или прошло", show_alert=False)

# --- 6. Show Times for Day (Level 2) ---
@router.callback_query(BookingStates.selecting_day, F.data.startswith("day_"))
async def show_day_times(callback: types.CallbackQuery, state: FSMContext):
    """Уровень 2: Показ времен для выбранного дня"""
    from datetime import datetime
    from handlers.master import get_weekday_for_date
    
    date_str = callback.data.split("_")[1]  # "DD.MM"
    
    data = await state.get_data()
    master_id = data.get("master_id")
    service_id = data.get("service_id")
    
    # Получаем длительность выбранной услуги
    svc_duration = 30
    if service_id:
        svc_info = await get_service_info(service_id)
        if svc_info and svc_info[2]:
            svc_duration = svc_info[2]
    
    slots = await get_available_slots(master_id, svc_duration)
    
    # Filter slots for this day
    day_slots = [(s_id, s_time) for s_id, s_time in slots if s_time.startswith(date_str)]
    
    if not day_slots:
        await callback.answer("На этот день нет окошек", show_alert=True)
        return
    
    # Sort by time
    day_slots.sort(key=lambda x: datetime.strptime(x[1], "%d.%m %H:%M"))
    
    # Get service info for title
    svc_info = await get_service_info(service_id)
    svc_name, svc_price, svc_dur, svc_desc, svc_cat, svc_subcat = svc_info
   
    cat_clean = svc_cat.split(' ', 1)[1] if ' ' in svc_cat else svc_cat
    if svc_subcat:
        full_title = f"{cat_clean} ({svc_subcat}) • {svc_name}"
    else:
        full_title = f"{cat_clean} • {svc_name}"
    
    # Build message
    weekday = get_weekday_for_date(date_str)
    title = f"✅ *{full_title}* — {int(svc_price)}₽\n\n"
    title += f"📅 *{weekday} {date_str}*\n\n"
    title += "🕐 Выберите время:"
    
    kb = InlineKeyboardBuilder()
    
    # Add time buttons (only time)
    for s_id, s_time in day_slots:
        time_only = s_time.split()[1]  # Extract "HH:MM"
        kb.button(text=time_only, callback_data=f"book_{s_id}")
    
    kb.button(text="⬅️ Назад к дням", callback_data="back_to_days")
    kb.adjust(4)  # 4 times per row
    
    await callback.message.edit_text(title, reply_markup=kb.as_markup())
    await state.set_state(BookingStates.selecting_slot)
    await callback.answer()

# --- Back to Days ---
@router.callback_query(BookingStates.selecting_slot, F.data == "back_to_days")
async def back_to_days_from_times(callback: types.CallbackQuery, state: FSMContext):
    """Возврат к выбору дня"""
    await show_slots_logic(callback.message, state, edit_message=True)
    await callback.answer()

@router.callback_query(F.data == "back_from_slots")
async def back_from_slots(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    master_id = data.get("master_id")
    category = data.get("category")
    subcategory = data.get("subcategory")
    
    await show_services(callback.message, master_id, category, subcategory, state, edit_message=True)
    await callback.answer()

@router.callback_query(F.data == "back_to_cats")
async def back_to_cats(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    master_id = data.get("master_id")
    await show_categories(callback.message, master_id, state, edit_message=True)
    await callback.answer()

@router.callback_query(F.data == "cancel_booking")
async def cancel_booking_flow(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Запись отменена.")
    await callback.answer()

# --- 6. Final Booking ---
@router.callback_query(F.data.startswith("book_"))
async def process_booking(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Show confirmation before final booking"""
    slot_id = int(callback.data.split("_")[1])
    
    data = await state.get_data()
    service_id = data.get("service_id")
    
    # Store slot_id for confirmation
    await state.update_data(pending_slot_id=slot_id)
    
    # Get slot and service info
    slot_info = await get_slot_info(slot_id)
    datetime_str = slot_info[0]
    
    svc_info = await get_service_info(service_id) if service_id else None
    if svc_info:
        svc_name, svc_price, svc_dur, svc_desc, svc_cat, svc_subcat = svc_info
        cat_clean = svc_cat.split(' ', 1)[1] if ' ' in svc_cat else svc_cat
        if svc_subcat:
            full_svc = f"{cat_clean} ({svc_subcat}) • {svc_name}"
        else:
            full_svc = f"{cat_clean} • {svc_name}"
    else:
        full_svc = "Услуга"
        svc_price = 0
    
    # Format with weekday
    from handlers.master import format_slot_with_weekday
    formatted_time = format_slot_with_weekday(datetime_str)
    
    # Build confirmation message
    msg = f"📋 *Подтверждение записи*\n\n"
    msg += f"📅 *Дата и время:* {formatted_time}\n"
    msg += f"💅 *Услуга:* {full_svc}\n"
    msg += f"💰 *Стоимость:* {int(svc_price)}₽\n\n"
    msg += "Все верно?"
    
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтверждаю", callback_data="confirm_booking")
    kb.button(text="❌ Отменить", callback_data="cancel_booking")
    kb.adjust(1)
    
    await callback.message.edit_text(msg, reply_markup=kb.as_markup())
    await state.set_state(BookingStates.confirming_booking)
    await callback.answer()

@router.callback_query(F.data == "confirm_booking")
async def confirm_booking(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Final booking after confirmation"""
    data = await state.get_data()
    slot_id = data.get("pending_slot_id")
    service_id = data.get("service_id")
    client_id = callback.from_user.id
    
    # КРИТИЧНО: Проверить что время слота еще не прошло
    slot_info = await get_slot_info(slot_id)
    if not slot_info:
        await callback.message.edit_text("❌ Слот не найден.")
        await state.clear()
        await callback.answer()
        return
    
    datetime_str = slot_info[0]
    
    # Проверка времени
    from datetime import datetime
    try:
        day_month, time = datetime_str.split()
        day, month = map(int, day_month.split('.'))
        hour, minute = map(int, time.split(':'))
        now = datetime.now()
        slot_dt = datetime(now.year, month, day, hour, minute)
        
        # Если слот в прошлом - отклонить
        if slot_dt <= now:
            await callback.message.edit_text(
                "❌ К сожалению, это время уже прошло.\n"
                "Пожалуйста, выберите другое окошко."
            )
            await state.clear()
            await callback.answer()
            return
    except:
        pass  # Если не удалось распарсить - продолжить (безопаснее)
    
    success = await book_slot(slot_id, client_id, service_id)
    
    if success:
        slot_info = await get_slot_info(slot_id)
        datetime_str = slot_info[0]
        
        svc_info = await get_service_info(service_id) if service_id else None
        if svc_info:
            svc_name, svc_price, svc_dur, svc_desc, svc_cat, svc_subcat = svc_info
            cat_clean = svc_cat.split(' ', 1)[1] if ' ' in svc_cat else svc_cat
            if svc_subcat:
                full_svc = f"{cat_clean} ({svc_subcat}) • {svc_name}"
            else:
                full_svc = f"{cat_clean} • {svc_name}"
        else:
            full_svc = "Услуга"
        
        from handlers.master import format_slot_with_weekday
        formatted_time = format_slot_with_weekday(datetime_str)
        
        msg = f"✅ *Вы успешно записаны!*\n\n📅 {formatted_time}\n💅 {full_svc}\n\nЖдем вас 💅"
        await callback.message.edit_text(msg)
        
        # Notify the correct Master (the one who owns the booked slot)
        user = callback.from_user
        client_link = f"@{user.username}" if user.username else f"[{user.full_name}](tg://user?id={user.id})"
        
        admin_text = f"🔔 *Новая запись!*\nКлиент: {client_link}\nВремя: {formatted_time}\nУслуга: {full_svc}"
            
        try:
            # Notify the master who owns this slot
            master_tg_id = await get_master_tg_id_by_slot_id(slot_id)
            if master_tg_id:
                await bot.send_message(chat_id=master_tg_id, text=admin_text)
            else:
                # Fallback to admin
                await bot.send_message(chat_id=ADMIN_ID, text=admin_text)
        except: pass
        
        # Sync booking to Google Calendar (safe — failure doesn't affect booking)
        try:
            from utils.google_calendar import create_calendar_event
            from database.db_cmds import get_master_google_calendar_id
            data = await state.get_data()
            master_id = data.get('master_id')
            if not master_id:
                raise Exception("Не найден master_id в FSM context (кто мастер?)")
            
            cal_id = await get_master_google_calendar_id(master_id)
            if not cal_id:
                raise Exception(f"У мастера ID={master_id} нет Google Calendar в базе.")
            if not svc_info:
                raise Exception("Не найдена информация об услуге (svc_info=None).")

            # datetime_str format: 'DD.MM HH:MM'
            date_part, time_part = datetime_str.split()
            duration = svc_info[2] if svc_info[2] else 60
            client_display = callback.from_user.full_name or callback.from_user.username or "Клиент"
            
            await create_calendar_event(
                calendar_id=cal_id,
                date_str=date_part,
                time_str=time_part,
                duration_minutes=duration,
                client_name=client_display,
                service_name=full_svc
            )
        except Exception as e:
            import logging
            logging.warning(f"Google Calendar sync after booking failed (non-critical): {e}")
            try:
                from config import ADMIN_ID
                await bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ Ошибка Google Calendar: {str(e)}")
            except: pass
    else:
        await callback.message.edit_text("❌ Упс, это окошко уже заняли.")
        
    await state.clear()
    await callback.answer()

# --- My Bookings ---
@router.message(F.text == "👤 Мои записи")
async def my_bookings(message: types.Message):
    bookings = await get_client_bookings(message.from_user.id)
    
    if not bookings:
        await message.answer("У вас пока нет активных записей 🤷‍♀️")
        return
    
    from handlers.master import format_slot_with_weekday
    
    # Build message with booking details
    text = "🗓 *Ваши записи:*\n\n"
    kb = InlineKeyboardBuilder()
    
    for slot_id, datetime_str, master_name, svc_name, svc_price, svc_cat, svc_subcat in bookings:
        formatted_time = format_slot_with_weekday(datetime_str)
        
        # Build full service title
        if svc_name:
            cat_clean = svc_cat.split(' ', 1)[1] if svc_cat and ' ' in svc_cat else (svc_cat or "")
            if svc_subcat:
                full_svc = f"{cat_clean} ({svc_subcat}) • {svc_name}"
            else:
                full_svc = f"{cat_clean} • {svc_name}" if cat_clean else svc_name
            
            text += f"📅 *{formatted_time}*\n💅 {full_svc}\n💰 {int(svc_price)}₽\n\n"
        else:
            text += f"📅 *{formatted_time}*\n\n"
        
        # Button with weekday
        kb.button(text=f"❌ {formatted_time}", callback_data=f"cancel_{slot_id}")
    
    kb.adjust(1)
    await message.answer(text + "_Нажмите на кнопку чтобы отменить_", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("cancel_"))
async def process_cancel(callback: types.CallbackQuery, bot: Bot):
    slot_id = int(callback.data.split("_")[-1])
    client_id = callback.from_user.id
    
    slot_info = await get_slot_info(slot_id)
    if not slot_info:
        await callback.answer("Ошибка: запись не найдена.")
        return
    
    datetime_str = slot_info[0]
    svc_name = slot_info[2] if len(slot_info) > 2 else None

    success = await cancel_booking_db(slot_id, client_id)
    
    if success:
        msg = f"🗑 Запись на *{datetime_str}* отменена."
        await callback.message.edit_text(msg)
        
        # Notify Admin
        user = callback.from_user
        client_link = f"@{user.username}" if user.username else f"[{user.full_name}](tg://user?id={user.id})"
        
        admin_msg = f"⚠️ *Запись отменена!*\nКлиент: {client_link}\nВремя: {datetime_str}"
        if svc_name:
             admin_msg += f"\nУслуга: {svc_name}" 
             
        try:
             await bot.send_message(chat_id=ADMIN_ID, text=admin_msg)
        except: pass
    else:
        await callback.answer("Не удалось отменить.")
    await callback.answer()
