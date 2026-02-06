"""
Slot Generator - Creates slots from weekly templates
"""
import aiosqlite
from datetime import datetime, timedelta
from database.setup import DB_NAME
from database.template_cmds import get_all_template_times, is_vacation_day
from database.db_cmds import get_master_id_by_tg_id

WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

async def generate_slots_from_template(master_tg_id: int, days_ahead: int = 30) -> dict:
    """
    Generate slots for the next N days based on weekly template.
    
    Returns:
        dict: {
            "created": int,  # Number of new slots created
            "skipped": int,  # Number of slots skipped (already exist or vacation)
            "errors": []     # List of error messages
        }
    """
    master_id = await get_master_id_by_tg_id(master_tg_id)
    if not master_id:
        return {"created": 0, "skipped": 0, "errors": ["Master not found"]}
    
    # Get template times
    template_times = await get_all_template_times(master_id)
    if not template_times:
        return {"created": 0, "skipped": 0, "errors": ["No template configured"]}
    
    # Organize by day of week
    template_by_day = {}
    for _, day_of_week, time in template_times:
        if day_of_week not in template_by_day:
            template_by_day[day_of_week] = []
        template_by_day[day_of_week].append(time)
    
    created = 0
    skipped = 0
    errors = []
    
    # Generate for each day
    start_date = datetime.now().date()
    
    async with aiosqlite.connect(DB_NAME) as db:
        for i in range(days_ahead):
            current_date = start_date + timedelta(days=i)
            day_of_week = current_date.weekday()  # 0=Mon, 6=Sun
            
            # Check if this day has template times
            if day_of_week not in template_by_day:
                continue
            
            # Format date as DD.MM.YYYY
            date_str = current_date.strftime("%d.%m.%Y")
            
            # Check if vacation day
            if await is_vacation_day(master_id, date_str):
                skipped += len(template_by_day[day_of_week])
                continue
            
            # Create slots for each time in template
            for time in template_by_day[day_of_week]:
                # Format: "DD.MM HH:MM"
                datetime_str = f"{current_date.strftime('%d.%m')} {time}"
                
                # Check if slot already exists
                async with db.execute(
                    "SELECT id FROM slots WHERE master_id = ? AND datetime = ?",
                    (master_id, datetime_str)
                ) as cursor:
                    if await cursor.fetchone():
                        skipped += 1
                        continue
                
                # Create slot
                try:
                    await db.execute(
                        "INSERT INTO slots (master_id, datetime, is_booked) VALUES (?, ?, 0)",
                        (master_id, datetime_str)
                    )
                    created += 1
                except Exception as e:
                    errors.append(f"Error creating slot {datetime_str}: {str(e)}")
        
        await db.commit()
    
    return {"created": created, "skipped": skipped, "errors": errors}
