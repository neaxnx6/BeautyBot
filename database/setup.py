import aiosqlite

DB_NAME = "beautybot.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # Table: Users (Clients)
        # Added linked_master_id
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                phone TEXT,
                linked_master_id INTEGER
            )
        ''')
        
        # Migration for existing DB (try/except safe check)
        try:
            await db.execute("ALTER TABLE users ADD COLUMN linked_master_id INTEGER")
        except:
            pass # Column likely exists
            
        # Table: Masters (Service Providers)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS masters (
                id INTEGER PRIMARY KEY,
                telegram_id INTEGER UNIQUE,
                name TEXT,
                description TEXT
            )
        ''')
        
        # Table: Services
        await db.execute('''
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                master_id INTEGER,
                category TEXT,
                subcategory TEXT,
                name TEXT,
                price REAL,
                duration INTEGER,
                description TEXT,
                FOREIGN KEY(master_id) REFERENCES masters(id)
            )
        ''')
        
        # Migration for existing services (try/except safe check)
        try:
            await db.execute("ALTER TABLE services ADD COLUMN subcategory TEXT")
        except:
            pass # Column likely exists

        # Table: Slots (Schedule)
        # Added service_id to track what is booked
        # Added blocked_by to track duration-based blocking
        await db.execute('''
            CREATE TABLE IF NOT EXISTS slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                master_id INTEGER,
                datetime TEXT,
                is_booked BOOLEAN DEFAULT 0,
                client_id INTEGER,
                service_id INTEGER,
                blocked_by INTEGER,
                FOREIGN KEY(master_id) REFERENCES masters(id),
                FOREIGN KEY(client_id) REFERENCES users(id),
                FOREIGN KEY(service_id) REFERENCES services(id),
                FOREIGN KEY(blocked_by) REFERENCES slots(id)
            )
        ''')
        
        # Migration for existing slots
        try:
            await db.execute("ALTER TABLE slots ADD COLUMN service_id INTEGER")
        except:
            pass
        try:
            await db.execute("ALTER TABLE slots ADD COLUMN blocked_by INTEGER")
        except:
            pass
        
        # Table: Schedule Template (Weekly recurring slots)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS schedule_template (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                master_id INTEGER,
                day_of_week INTEGER,
                time TEXT,
                FOREIGN KEY(master_id) REFERENCES masters(id)
            )
        ''')
        
        # Table: Vacation Days (Days when master is unavailable)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS vacation_days (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                master_id INTEGER,
                date TEXT,
                FOREIGN KEY(master_id) REFERENCES masters(id)
            )
        ''')
        
        # Table: Master Settings
        await db.execute('''
            CREATE TABLE IF NOT EXISTS master_settings (
                master_id INTEGER PRIMARY KEY,
                min_booking_hours INTEGER DEFAULT 0,
                FOREIGN KEY(master_id) REFERENCES masters(id)
            )
        ''')
        
        # Table: Reminders (Track sent notifications)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_id INTEGER,
                client_id INTEGER,
                reminder_type TEXT,
                sent BOOLEAN DEFAULT 0,
                sent_at TEXT,
                FOREIGN KEY(slot_id) REFERENCES slots(id),
                FOREIGN KEY(client_id) REFERENCES users(id)
            )
        ''')

        await db.commit()
    print("Database initialized.")
