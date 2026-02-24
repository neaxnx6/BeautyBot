import aiosqlite
from database.setup import DB_NAME
from typing import Optional, List, Tuple
from datetime import datetime

# --- User Management ---
async def add_user(user_id: int, username: str, full_name: str, deep_link_master: int = None):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (id, username, full_name) VALUES (?, ?, ?)", (user_id, username, full_name))
        if deep_link_master:
             await db.execute("UPDATE users SET linked_master_id = ? WHERE id = ?", (deep_link_master, user_id))
        await db.commit()

async def get_user_master(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT linked_master_id FROM users WHERE id = ?", (user_id,)) as cursor:
             result = await cursor.fetchone()
             return result[0] if result else None

# --- Master Management ---
async def get_master_by_tg_id(telegram_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM masters WHERE telegram_id = ?", (telegram_id,)) as cursor:
            return await cursor.fetchone()

async def get_master_id_by_tg_id(telegram_id: int):
    row = await get_master_by_tg_id(telegram_id)
    return row[0] if row else None

async def get_master_name_by_id(master_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT name FROM masters WHERE id = ?", (master_id,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else "Мастер"

async def register_master(telegram_id: int, name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO masters (telegram_id, name) VALUES (?, ?)", (telegram_id, name))
        await db.commit()

# --- Services Management (New) ---
async def get_service_categories(master_id: int) -> List[str]:
    """Get all service categories in desired order."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT DISTINCT category FROM services WHERE master_id = ?", (master_id,)) as cursor:
            rows = await cursor.fetchall()
            categories = [row[0] for row in rows]
            
            # Custom order
            order = ["🫶🏻 Комплекс", "💅 Маникюр", "🐾 Педикюр", "💌 Другое", "⛓ Мужской"]
            return sorted(categories, key=lambda x: order.index(x) if x in order else 999)

async def get_subcategories(master_id: int, category: str) -> List[str]:
    """Get subcategories for a category (returns empty if none)."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT DISTINCT subcategory FROM services WHERE master_id = ? AND category = ? AND subcategory IS NOT NULL ORDER BY subcategory",
            (master_id, category)
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def get_services_in_category(master_id: int, category: str, subcategory: str = None):
    """Get services, optionally filtered by subcategory."""
    async with aiosqlite.connect(DB_NAME) as db:
        if subcategory:
            query = "SELECT id, name, price, duration, description, subcategory FROM services WHERE master_id = ? AND category = ? AND subcategory = ?"
            params = (master_id, category, subcategory)
        else:
            query = "SELECT id, name, price, duration, description, subcategory FROM services WHERE master_id = ? AND category = ? AND subcategory IS NULL"
            params = (master_id, category)
        
        async with db.execute(query, params) as cursor:
            return await cursor.fetchall()

async def get_service_info(service_id: int):
    """Returns (name, price, duration, description, category, subcategory)"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT name, price, duration, description, category, subcategory FROM services WHERE id = ?",
            (service_id,)
        ) as cursor:
            return await cursor.fetchone()

# --- Slot Management ---
async def add_slot(master_tg_id: int, datetime_str: str):
    master = await get_master_by_tg_id(master_tg_id)
    if not master: return False
    master_id = master[0]
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id FROM slots WHERE master_id = ? AND datetime = ?", (master_id, datetime_str)) as cursor:
            if await cursor.fetchone():
                return "duplicate"
        await db.execute("INSERT INTO slots (master_id, datetime, is_booked) VALUES (?, ?, 0)", (master_id, datetime_str))
        await db.commit()
    return True

async def delete_slot_db(slot_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id FROM slots WHERE id = ?", (slot_id,)) as cursor:
            if not await cursor.fetchone(): return False
        await db.execute("DELETE FROM slots WHERE id = ?", (slot_id,))
        await db.commit()
        return True

async def get_master_slots_with_ids(master_tg_id: int):
    """Get master slots with booking details: (slot_id, datetime, is_booked, client_id, client_name, client_username, service_name, service_price)"""
    master = await get_master_by_tg_id(master_tg_id)
    if not master: return []
    master_id = master[0]
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('''
            SELECT 
                slots.id, 
                slots.datetime, 
                slots.is_booked, 
                slots.client_id,
                users.full_name,
                users.username,
                services.name,
                services.price,
                services.category,
                services.subcategory
            FROM slots 
            LEFT JOIN users ON slots.client_id = users.id
            LEFT JOIN services ON slots.service_id = services.id
            WHERE slots.master_id = ? 
            ORDER BY slots.datetime
        ''', (master_id,)) as cursor:
            return await cursor.fetchall()

async def get_all_masters():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, name FROM masters") as cursor:
            return await cursor.fetchall()

async def get_available_slots(master_id: int):
    """Get available slots, respecting minimum booking time"""
    from database.template_cmds import get_master_settings
    from datetime import datetime, timedelta
    
    min_hours = await get_master_settings(master_id)
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id, datetime FROM slots WHERE master_id = ? AND is_booked = 0 ORDER BY datetime", 
            (master_id,)
        ) as cursor:
            all_slots = await cursor.fetchall()
    
    # Всегда фильтровать прошедшее время + добавить мин. ограничение мастера
    now = datetime.now()
    min_booking_time = now + timedelta(hours=min_hours)
    
    filtered_slots = []
    for slot_id, datetime_str in all_slots:
        try:
            day_month, time = datetime_str.split()
            day, month = map(int, day_month.split('.'))
            hour, minute = map(int, time.split(':'))
            
            slot_dt = datetime(now.year, month, day, hour, minute)
            
            # Слот в прошлом — пропускаем (не показываем клиенту)
            if slot_dt <= now:
                continue
            
            # Слот должен быть дальше чем min_hours от текущего времени
            if slot_dt > min_booking_time:
                filtered_slots.append((slot_id, datetime_str))
        except:
            continue
    
    return filtered_slots

async def book_slot(slot_id: int, client_id: int, service_id: int = None):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT is_booked FROM slots WHERE id = ?", (slot_id,)) as cursor:
            result = await cursor.fetchone()
            if not result or result[0] == 1: return False
            
        await db.execute("UPDATE slots SET is_booked = 1, client_id = ?, service_id = ? WHERE id = ?", (client_id, service_id, slot_id))
        await db.commit()
        return True

async def get_slot_info(slot_id: int):
    """Returns (datetime, master_id, service_name, price)"""
    async with aiosqlite.connect(DB_NAME) as db:
        # Join with services to get details
        async with db.execute('''
            SELECT slots.datetime, slots.master_id, services.name, services.price 
            FROM slots 
            LEFT JOIN services ON slots.service_id = services.id 
            WHERE slots.id = ?
        ''', (slot_id,)) as cursor:
            return await cursor.fetchone()

async def get_client_bookings(client_id: int):
    """Get client bookings with full service details"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('''
            SELECT 
                slots.id, 
                slots.datetime, 
                masters.name, 
                services.name, 
                services.price,
                services.category,
                services.subcategory
            FROM slots 
            JOIN masters ON slots.master_id = masters.id 
            LEFT JOIN services ON slots.service_id = services.id
            WHERE slots.client_id = ? AND slots.is_booked = 1 
            ORDER BY slots.datetime
        ''', (client_id,)) as cursor:
            return await cursor.fetchall()

async def cancel_booking_db(slot_id: int, client_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id FROM slots WHERE id = ? AND client_id = ? AND is_booked = 1", (slot_id, client_id)) as cursor:
            if not await cursor.fetchone(): return False
        # Clear service_id too
        await db.execute("UPDATE slots SET is_booked = 0, client_id = NULL, service_id = NULL WHERE id = ?", (slot_id,))
        await db.commit()
        return True
