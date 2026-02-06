import aiosqlite
from database.setup import DB_NAME
from typing import List, Tuple
from datetime import datetime, timedelta

# --- Schedule Template Management ---

async def add_template_time(master_id: int, day_of_week: int, time: str):
    """Add a time slot to weekly template. day_of_week: 0=Mon, 6=Sun"""
    async with aiosqlite.connect(DB_NAME) as db:
        # Check for duplicate
        async with db.execute(
            "SELECT id FROM schedule_template WHERE master_id = ? AND day_of_week = ? AND time = ?",
            (master_id, day_of_week, time)
        ) as cursor:
            if await cursor.fetchone():
                return "duplicate"
        
        await db.execute(
            "INSERT INTO schedule_template (master_id, day_of_week, time) VALUES (?, ?, ?)",
            (master_id, day_of_week, time)
        )
        await db.commit()
    return True

async def get_template_times(master_id: int, day_of_week: int) -> List[Tuple[int, str]]:
    """Get all template times for a specific day. Returns [(id, time), ...]"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id, time FROM schedule_template WHERE master_id = ? AND day_of_week = ? ORDER BY time",
            (master_id, day_of_week)
        ) as cursor:
            return await cursor.fetchall()

async def get_all_template_times(master_id: int) -> List[Tuple[int, int, str]]:
    """Get all template times for all days. Returns [(id, day_of_week, time), ...]"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id, day_of_week, time FROM schedule_template WHERE master_id = ? ORDER BY day_of_week, time",
            (master_id,)
        ) as cursor:
            return await cursor.fetchall()

async def delete_template_time(template_id: int):
    """Delete a template time slot"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM schedule_template WHERE id = ?", (template_id,))
        await db.commit()
    return True

# --- Vacation Days Management ---

async def add_vacation_day(master_id: int, date: str):
    """Add a vacation day. date format: 'DD.MM.YYYY'"""
    async with aiosqlite.connect(DB_NAME) as db:
        # Check for duplicate
        async with db.execute(
            "SELECT id FROM vacation_days WHERE master_id = ? AND date = ?",
            (master_id, date)
        ) as cursor:
            if await cursor.fetchone():
                return "duplicate"
        
        await db.execute(
            "INSERT INTO vacation_days (master_id, date) VALUES (?, ?)",
            (master_id, date)
        )
        await db.commit()
    return True

async def get_vacation_days(master_id: int) -> List[Tuple[int, str]]:
    """Get all vacation days. Returns [(id, date), ...]"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id, date FROM vacation_days WHERE master_id = ? ORDER BY date",
            (master_id,)
        ) as cursor:
            return await cursor.fetchall()

async def delete_vacation_day(vacation_id: int):
    """Delete a vacation day"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM vacation_days WHERE id = ?", (vacation_id,))
        await db.commit()
    return True

async def is_vacation_day(master_id: int, date: str) -> bool:
    """Check if a specific date is a vacation day"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id FROM vacation_days WHERE master_id = ? AND date = ?",
            (master_id, date)
        ) as cursor:
            return await cursor.fetchone() is not None

# --- Master Settings ---

async def get_master_settings(master_id: int) -> int:
    """Get minimum booking hours for master. Returns 0 if not set."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT min_booking_hours FROM master_settings WHERE master_id = ?",
            (master_id,)
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0

async def set_min_booking_hours(master_id: int, hours: int):
    """Set minimum booking hours (0 = disabled)"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO master_settings (master_id, min_booking_hours) VALUES (?, ?)",
            (master_id, hours)
        )
        await db.commit()
    return True
