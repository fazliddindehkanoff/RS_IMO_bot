"""Bot setup for webhook mode."""
import logging
from django.conf import settings

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.handlers import registration, test, feedback, admin

logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()

# Register routers
dp.include_router(admin.router)  # Admin router should be first to have priority
dp.include_router(registration.router)
dp.include_router(test.router)
dp.include_router(feedback.router)

# Track initialization status
_initialized = False


async def init_bot():
    """Initialize bot (database, etc.)"""
    global _initialized
    if _initialized:
        return
    
    logger.info("Initializing bot...")
    # Database is managed by Django migrations
    # Add any additional bot initialization here
    logger.info("Bot initialized.")
    _initialized = True
