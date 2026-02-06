import csv
import asyncio
import aiosqlite
import sys
import os

# Add parent directory to path to import database.setup
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.setup import DB_NAME, init_db

CSV_FILE = "services_template.csv"

async def import_services():
    # Ensure DB is ready
    await init_db()
    
    # Read CSV
    services = []
    try:
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                services.append(row)
    except FileNotFoundError:
        print(f"Error: {CSV_FILE} not found!")
        return

    if not services:
        print("No services found in CSV.")
        return

    async with aiosqlite.connect(DB_NAME) as db:
        # Clear existing services (Full Refresh Strategy)
        await db.execute("DELETE FROM services")
        
        # Get Admin Master ID (Assumption: We attach to the first master found or ID 1)
        # For SaaS, we would look up by some identifier. Here we just assign to all masters or specific one.
        # Let's assign to ALL existing masters for now (since we only have 1 active master usually).
        async with db.execute("SELECT id FROM masters") as cursor:
            masters = await cursor.fetchall()
            
        if not masters:
            print("No masters found in DB! Please register a master first (run bot).")
            return

        print(f"Found {len(masters)} masters. Importing {len(services)} services for each...")

        count = 0
        for master_id_tuple in masters:
            master_id = master_id_tuple[0]
            for s in services:
                # CSV: Категория,Подкатегория,Название,Цена,Длительность,Описание
                category = s.get('Категория', '').strip()
                subcategory = s.get('Подкатегория', '').strip() or None  # Empty string -> None
                name = s.get('Название', '').strip()
                price = float(s.get('Цена', '0').replace(' ', '').replace(',', '.'))
                duration = int(s.get('Длительность', '0'))
                description = s.get('Описание', '').strip()

                await db.execute('''
                    INSERT INTO services (master_id, category, subcategory, name, price, duration, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (master_id, category, subcategory, name, price, duration, description))
                count += 1
        
        await db.commit()
        print(f"✅ Successfully imported {count} services!")

if __name__ == "__main__":
    asyncio.run(import_services())
