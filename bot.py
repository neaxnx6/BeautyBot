import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from database.setup import init_db

# Configure logging
logging.basicConfig(level=logging.INFO)

async def main():
    # 1. Initialize Database
    await init_db()

    # 2. Check Token
    if not BOT_TOKEN:
        print("Error: Please set BOT_TOKEN in .env file")
        return

    # 3. Start Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    dp = Dispatcher()
    
    # Запуск системы напоминаний
    start_reminder_scheduler(bot) # Added call to scheduler
    
    print("Bot is running...")
    
    from handlers.start import router as start_router
    from handlers.master import router as master_router
    from handlers.client import router as client_router
    from handlers.template import router as template_router
    
    dp.include_router(start_router)
    dp.include_router(master_router)
    dp.include_router(client_router)
    dp.include_router(template_router)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped")
