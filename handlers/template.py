from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

from database.template_cmds import (
    add_template_time, get_template_times, get_all_template_times, delete_template_time,
    add_vacation_day, get_vacation_days, delete_vacation_day,
    get_master_settings, set_min_booking_hours
)
from database.db_cmds import get_master_id_by_tg_id, get_master_by_tg_id
from utils.slot_generator import generate_slots_from_template
from keyboards.template import (
    weekly_template_kb, day_time_selector_kb, generation_period_kb,
    min_booking_time_kb, vacation_management_kb, other_menu_kb
)
from keyboards.master import build_date_keyboard

router = Router()

WEEKDAYS_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

class TemplateStates(StatesGroup):
    selecting_times = State()
    adding_vacation = State()

# --- Helper Functions ---
async def get_day_counts(master_id: int) -> dict:
    """Get slot countsfor each day of week"""
    counts = {}
    for day in range(7):
        times = await get_template_times(master_id, day)
        counts[day] = len(times)
    return counts

# --- Main Template Menu ---
@router.message(F.text == "🗓 Шаблон")
async def show_weekly_template(message: types.Message):
    master_id = await get_master_id_by_tg_id(message.from_user.id)
    counts = await get_day_counts(master_id)
    
    text = "📋 *Шаблон Недели*\n\nВыберите день для настройки:"
    await message.answer(text, reply_markup=weekly_template_kb(counts))

@router.callback_query(F.data == "back_to_template")
async def back_to_template(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    master_id = await get_master_id_by_tg_id(callback.from_user.id)
    counts = await get_day_counts(master_id)
    
    text = "📋 *Шаблон Недели*\n\nВыберите день для настройки:"
    await callback.message.edit_text(text, reply_markup=weekly_template_kb(counts))
    await callback.answer()

# --- Day Time Selection (Multiple) ---
@router.callback_query(F.data.startswith("day_"))
async def show_day_times(callback: types.CallbackQuery, state: FSMContext):
    day_of_week = int(callback.data.split("_")[1])
    master_id = await get_master_id_by_tg_id(callback.from_user.id)
    
    # Get existing times for this day
    times_data = await get_template_times(master_id, day_of_week)
    selected_times = [time for _, time in times_data]
    
    await state.update_data(day_of_week=day_of_week, selected_times=selected_times)
    await state.set_state(TemplateStates.selecting_times)
    
    text = f"⏰ *{WEEKDAYS_RU[day_of_week]}*\n\nВыберите время окошек:\n\nВыбрано: {len(selected_times)} окошка"
    await callback.message.edit_text(text, reply_markup=day_time_selector_kb(day_of_week, selected_times))
    await callback.answer()

@router.callback_query(TemplateStates.selecting_times, F.data.startswith("toggle_time_"))
async def toggle_time(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    day_of_week = int(parts[2])
    time = parts[3]
    
    data = await state.get_data()
    selected_times = data.get("selected_times", [])
    
    # Toggle
    if time in selected_times:
        selected_times.remove(time)
    else:
        selected_times.append(time)
    
    await state.update_data(selected_times=selected_times)
    
    # Update message
    text = f"⏰ *{WEEKDAYS_RU[day_of_week]}*\n\nВыберите время окошек:\n\nВыбрано: {len(selected_times)} окошка"
    await callback.message.edit_text(text, reply_markup=day_time_selector_kb(day_of_week, selected_times))
    await callback.answer()

@router.callback_query(TemplateStates.selecting_times, F.data.startswith("confirm_times_"))
async def confirm_times(callback: types.CallbackQuery, state: FSMContext):
    day_of_week = int(callback.data.split("_")[2])
    data = await state.get_data()
    selected_times = data.get("selected_times", [])
    
    master_id = await get_master_id_by_tg_id(callback.from_user.id)
    
    # Delete all existing times for this day
    existing = await get_template_times(master_id, day_of_week)
    for template_id, _ in existing:
        await delete_template_time(template_id)
    
    # Add new times
    for time in selected_times:
        await add_template_time(master_id, day_of_week, time)
    
    await state.clear()
    
    # Return to template menu
    counts = await get_day_counts(master_id)
    text = "📋 *Шаблон Недели*\n\nВыберите день для настройки:"
    await callback.message.edit_text(text, reply_markup=weekly_template_kb(counts))
    await callback.answer("✅ Окошки сохранены!")

# --- Generation ---
@router.callback_query(F.data == "template_generate")
async def show_generation(callback: types.CallbackQuery):
    text = "🔄 *Генерация Окошек*\n\n"
    text += "Выберите период для генерации:\n\n"
    text += "⚠️ Окошки будут созданы на основе шаблона недели.\n"
    text += "Уже существующие окошки не будут затронуты."
    
    await callback.message.edit_text(text, reply_markup=generation_period_kb())
    await callback.answer()

@router.callback_query(F.data.startswith("gen_"))
async def process_generation(callback: types.CallbackQuery):
    days = int(callback.data.split("_")[1])
    
    await callback.answer("Генерация началась...")
    
    result = await generate_slots_from_template(callback.from_user.id, days)
    
    master_id = await get_master_id_by_tg_id(callback.from_user.id)
    counts = await get_day_counts(master_id)
    
    text = "✅ *Генерация завершена!*\n\n"
    text += f"Создано окошек: {result['created']}\n"
    text += f"Пропущено: {result['skipped']}\n"
    
    if result['errors']:
        text += f"\nОшибки: {len(result['errors'])}"
    
    text += "\n\n📋 *Шаблон Недели*\n\nВыберите день для настройки:"
    
    await callback.message.edit_text(text, reply_markup=weekly_template_kb(counts))

# --- Vacation Days ---
# Vacation handlers removed - functionality moved to "Clear day" in schedule
# Users can delete entire days from "Мое Расписание" instead



@router.callback_query(F.data == "add_vacation")
async def start_add_vacation(callback: types.CallbackQuery, state: FSMContext):
    kb = build_date_keyboard()
    text = "📅 Выберите дату выходного:"
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await state.set_state(TemplateStates.adding_vacation)
    await callback.answer()

@router.callback_query(TemplateStates.adding_vacation, F.data.startswith("date_"))
async def process_add_vacation(callback: types.CallbackQuery, state: FSMContext):
    date_str = callback.data.split("_")[1]  # YYYY-MM-DD
    master_id = await get_master_id_by_tg_id(callback.from_user.id)
    
    # Convert to DD.MM.YYYY
    from datetime import datetime
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    date_formatted = date_obj.strftime("%d.%m.%Y")
    
    result = await add_vacation_day(master_id, date_formatted)
    
    await state.clear()
    
    vacations = await get_vacation_days(master_id)
    text = "🏖 *Выходные Дни*\n\n"
    if vacations:
        text += "Текущие:\n"
        for _, d in vacations:
            text += f"• {d}\n"
    else:
        text += "_Выходные не заданы_"
    
    await callback.message.edit_text(text, reply_markup=vacation_management_kb())
    
    if result == "duplicate":
        await callback.answer("Этот день уже добавлен!", show_alert=True)
    else:
        await callback.answer("✅ Выходной добавлен!")

@router.callback_query(F.data == "del_vacation")
async def start_delete_vacation(callback: types.CallbackQuery):
    master_id = await get_master_id_by_tg_id(callback.from_user.id)
    vacations = await get_vacation_days(master_id)
    
    if not vacations:
        await callback.answer("Нет выходных для удаления!", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    for vac_id, date in vacations:
        kb.button(text=f"🗑 {date}", callback_data=f"delvac_{vac_id}")
    kb.button(text="⬅️ Назад", callback_data="template_vacations")
    kb.adjust(2, 1)
    
    text = "🗑 *Удалить выходной*\n\nВыберите дату:"
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("delvac_"))
async def process_delete_vacation(callback: types.CallbackQuery):
    vac_id = int(callback.data.split("_")[1])
    await delete_vacation_day(vac_id)
    
    master_id = await get_master_id_by_tg_id(callback.from_user.id)
    vacations = await get_vacation_days(master_id)
    
    text = "🏖 *Выходные Дни*\n\n"
    if vacations:
        text += "Текущие:\n"
        for _, d in vacations:
            text += f"• {d}\n"
    else:
        text += "_Выходные не заданы_"
    
    await callback.message.edit_text(text, reply_markup=vacation_management_kb())
    await callback.answer("✅ Выходной удален!")

# --- Other Menu ---
@router.message(F.text == "⚙️ Настройки")
async def show_other_menu(message: types.Message):
    text = "📎 *Дополнительно*\n\nВыберите раздел:"
    await message.answer(text, reply_markup=other_menu_kb())

@router.callback_query(F.data == "back_to_other")
async def back_to_other(callback: types.CallbackQuery):
    text = "📎 *Дополнительно*\n\nВыберите раздел:"
    await callback.message.edit_text(text, reply_markup=other_menu_kb())
    await callback.answer()

@router.callback_query(F.data == "back_to_master_panel")
async def back_to_panel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer()

@router.callback_query(F.data == "my_link")
async def show_my_link(callback: types.CallbackQuery):
    master = await get_master_by_tg_id(callback.from_user.id)
    if not master:
        await callback.answer("Ошибка: мастер не найден")
        return
    
    master_id = master[0]
    link = f"https://t.me/yes_girls_nails_bot?start=master_{master_id}"
    
    text = f"🔗 *Ваша ссылка для записи:*\n\n`{link}`\n\nОтправьте эту ссылку клиентам для записи."
    
    await callback.message.edit_text(text, reply_markup=other_menu_kb())
    await callback.answer()

# --- Minimum Booking Time ---
@router.callback_query(F.data == "template_min_time")
async def show_min_time(callback: types.CallbackQuery):
    master_id = await get_master_id_by_tg_id(callback.from_user.id)
    current = await get_master_settings(master_id)
    
    text = "⏰ *Минимальное время до записи*\n\n"
    if current == 0:
        text += "Текущее: ❌ Отключено\n\n"
    else:
        text += f"Текущее: {current} часов\n\n"
    
    text += "Клиенты не смогут записаться позже установленного времени до окошка."
    
    await callback.message.edit_text(text, reply_markup=min_booking_time_kb())
    await callback.answer()

@router.callback_query(F.data.startswith("mintime_"))
async def process_min_time(callback: types.CallbackQuery):
    hours = int(callback.data.split("_")[1])
    master_id = await get_master_id_by_tg_id(callback.from_user.id)
    
    await set_min_booking_hours(master_id, hours)
    
    text = "⏰ *Минимальное время до записи*\n\n"
    if hours == 0:
        text += "Текущее: ❌ Отключено\n\n"
        text += "Клиенты могут записываться в любое время."
    else:
        text += f"Текущее: {hours} часов\n\n"
        text += f"Клиенты не смогут записаться позже чем за {hours}ч до окошка."
    
    await callback.message.edit_text(text, reply_markup=min_booking_time_kb())
    await callback.answer("✅ Настройка сохранена!")
