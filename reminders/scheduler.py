"""
Система напоминаний для BeautyBot
Отправляет уведомления клиентам за 24 часа и за 3 часа до записи
"""
import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
import aiosqlite
from database.setup import DB_NAME

async def get_upcoming_bookings(hours_ahead: int):
    """Получить записи на ближайшие N часов"""
    async with aiosqlite.connect(DB_NAME) as db:
        query = '''
            SELECT 
                slots.id,
                slots.client_id,
                slots.datetime,
                services.name,
                masters.name
            FROM slots
            JOIN services ON slots.service_id = services.id
            JOIN masters ON slots.master_id = masters.id
            WHERE slots.is_booked = 1
        '''
        async with db.execute(query) as cursor:
            return await cursor.fetchall()

def parse_slot_datetime(datetime_str: str) -> datetime:
    """
    Парсит строку типа "10.02 14:00" в datetime объект
    Предполагаем текущий год
    """
    try:
        day_month, time = datetime_str.split()
        day, month = map(int, day_month.split('.'))
        hour, minute = map(int, time.split(':'))
        
        # Используем текущий год, но если месяц уже прошел, берем следующий год
        current_year = datetime.now().year
        slot_dt = datetime(current_year, month, day, hour, minute)
        
        # Если дата в прошлом, предполагаем следующий год
        if slot_dt < datetime.now():
            slot_dt = datetime(current_year + 1, month, day, hour, minute)
        
        return slot_dt
    except Exception as e:
        print(f"Ошибка парсинга даты {datetime_str}: {e}")
        return None

async def check_if_reminder_sent(slot_id: int, reminder_type: str) -> bool:
    """Проверить, было ли отправлено напоминание"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id FROM reminders WHERE slot_id = ? AND reminder_type = ? AND sent = 1",
            (slot_id, reminder_type)
        ) as cursor:
            result = await cursor.fetchone()
            return result is not None

async def mark_reminder_sent(slot_id: int, client_id: int, reminder_type: str):
    """Отметить напоминание как отправленное"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            '''INSERT INTO reminders (slot_id, client_id, reminder_type, sent, sent_at)
               VALUES (?, ?, ?, 1, ?)''',
            (slot_id, client_id, reminder_type, datetime.now().isoformat())
        )
        await db.commit()

async def send_reminder(bot: Bot, client_id: int, datetime_str: str, service_name: str, master_name: str, reminder_type: str):
    """Отправить напоминание клиенту"""
    try:
        if reminder_type == '24h':
            text = (
                f"🔔 <b>Напоминание о записи</b>\n\n"
                f"Завтра в <b>{datetime_str.split()[1]}</b> у вас запись:\n"
                f"📋 {service_name}\n"
                f"👤 Мастер: {master_name}\n\n"
                f"Ждём вас! 💅"
            )
        else:  # 3h
            text = (
                f"⏰ <b>Скоро ваша запись!</b>\n\n"
                f"Сегодня в <b>{datetime_str.split()[1]}</b>:\n"
                f"📋 {service_name}\n"
                f"👤 Мастер: {master_name}\n\n"
                f"До встречи! 💅"
            )
        
        await bot.send_message(client_id, text, parse_mode='HTML')
        print(f"✅ Напоминание {reminder_type} отправлено клиенту {client_id}")
    except Exception as e:
        print(f"❌ Ошибка отправки напоминания клиенту {client_id}: {e}")

async def check_and_send_reminders(bot: Bot):
    """
    Основная функция проверки и отправки напоминаний
    Вызывается периодически (каждые 30 минут)
    """
    print("🔍 Проверка напоминаний...")
    now = datetime.now()
    
    # Получаем все активные записи
    bookings = await get_upcoming_bookings(48)
    
    for booking in bookings:
        slot_id, client_id, datetime_str, service_name, master_name = booking
        
        # Парсим дату записи
        slot_dt = parse_slot_datetime(datetime_str)
        if not slot_dt:
            continue
        
        # Разница во времени
        time_diff = slot_dt - now
        
        # Напоминание за 24 часа (в диапазоне 23-24.5 часов)
        if timedelta(hours=23) <= time_diff < timedelta(hours=24, minutes=30):
            if not await check_if_reminder_sent(slot_id, '24h'):
                await send_reminder(bot, client_id, datetime_str, service_name, master_name, '24h')
                await mark_reminder_sent(slot_id, client_id, '24h')
        
        # Напоминание за 3 часа (в диапазоне 2.5-3.5 часов)
        if timedelta(hours=2, minutes=30) <= time_diff < timedelta(hours=3, minutes=30):
            if not await check_if_reminder_sent(slot_id, '3h'):
                await send_reminder(bot, client_id, datetime_str, service_name, master_name, '3h')
                await mark_reminder_sent(slot_id, client_id, '3h')

def start_reminder_scheduler(bot: Bot):
    """
    Запустить планировщик напоминаний
    Проверка каждые 30 минут
    """
    scheduler = AsyncIOScheduler()
    
    # Добавляем задачу проверки напоминаний каждые 30 минут
    scheduler.add_job(
        check_and_send_reminders,
        'interval',
        minutes=30,
        args=[bot],
        id='reminder_check',
        replace_existing=True
    )
    
    # Также делаем первую проверку сразу при запуске (через 1 минуту)
    scheduler.add_job(
        check_and_send_reminders,
        'date',
        run_date=datetime.now() + timedelta(minutes=1),
        args=[bot],
        id='initial_reminder_check'
    )
    
    scheduler.start()
    print("✅ Планировщик напоминаний запущен (проверка каждые 30 минут)")
