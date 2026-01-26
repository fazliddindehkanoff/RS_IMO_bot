"""Utility functions for admin panel."""
import asyncio
import logging
import time
from pathlib import Path
from django.conf import settings
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile

logger = logging.getLogger(__name__)


def send_test_assignment_message(telegram_id: int, test, with_start_button: bool = False):
    """
    Send test assignment message to user via Telegram.

    Args:
        telegram_id: User's Telegram ID
        test: Test model instance
        with_start_button: If True, attach inline "Boshlash" button to start the test
    """
    from bot.keyboards import get_start_test_keyboard

    async def _send_message():
        bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )

        message_text = (
            f"📝 <b>Yangi test yuborildi!</b>\n\n"
            f"<b>Test:</b> {test.title}\n"
            f"<b>Sinf:</b> {test.get_grade_display()}\n"
            f"<b>Davomiyligi:</b> {test.duration_minutes} daqiqa\n"
            f"<b>Savollar soni:</b> {test.get_questions_count()}\n\n"
            "Testni boshlash uchun quyidagi <b>Boshlash</b> tugmasini bosing yoki "
            "bottda /start → Imtihonlar bo'limiga o'ting."
        )

        reply_markup = get_start_test_keyboard() if with_start_button else None

        try:
            await bot.send_message(
                chat_id=telegram_id,
                text=message_text,
                reply_markup=reply_markup,
            )
            logger.info("Test assignment message sent to %s", telegram_id)
        except Exception as e:
            logger.error("Failed to send message to %s: %s", telegram_id, e)
            raise
        finally:
            await bot.session.close()
    
    # Run async function in sync context
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        # If loop is already running, use run_coroutine_threadsafe
        import threading
        future = asyncio.run_coroutine_threadsafe(_send_message(), loop)
        future.result()
    else:
        loop.run_until_complete(_send_message())


def send_certificate_message(telegram_id: int, certificate_image_path: str, delay_seconds: float = 1.0):
    """
    Send certificate image to user via Telegram with rate limiting.
    
    Args:
        telegram_id: User's Telegram ID
        certificate_image_path: Path to certificate image file (relative to MEDIA_ROOT or absolute)
        delay_seconds: Delay before sending (for rate limiting)
    """
    async def _send_certificate():
        bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )

        # Get absolute path
        if not Path(certificate_image_path).is_absolute():
            image_path = Path(settings.MEDIA_ROOT) / certificate_image_path
        else:
            image_path = Path(certificate_image_path)
        
        if not image_path.exists():
            logger.error("Certificate image not found: %s", image_path)
            raise FileNotFoundError(f"Certificate image not found: {image_path}")

        message_text = (
            "🎓 <b>Tabriklaymiz!</b>\n\n"
            "Sizning test natijangiz bo'yicha sertifikat tayyorlandi.\n\n"
            "Quyida sizning sertifikatingiz:"
        )

        try:
            # Add delay for rate limiting
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)
            
            # Use FSInputFile to properly send the photo
            photo = FSInputFile(str(image_path))
            await bot.send_photo(
                chat_id=telegram_id,
                photo=photo,
                caption=message_text,
            )
            logger.info("Certificate sent to %s", telegram_id)
        except Exception as e:
            logger.error("Failed to send certificate to %s: %s", telegram_id, e)
            raise
        finally:
            await bot.session.close()
    
    # Run async function in sync context
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        # If loop is already running, use run_coroutine_threadsafe
        import threading
        future = asyncio.run_coroutine_threadsafe(_send_certificate(), loop)
        future.result()
    else:
        loop.run_until_complete(_send_certificate())
