"""Polling mode for bot testing."""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'exam_bot_admin.settings')
import django
django.setup()

from django.conf import settings
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.handlers import registration, test
from exam_bot_admin.webhook import init_bot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Run bot in polling mode."""
    # Initialize bot
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    
    # Create dispatcher
    dp = Dispatcher()
    
    # Register routers
    dp.include_router(registration.router)
    dp.include_router(test.router)
    
    # Initialize bot (database, etc.)
    await init_bot()
    
    logger.info("Bot started in polling mode. Press Ctrl+C to stop.")
    
    # Start polling
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())
