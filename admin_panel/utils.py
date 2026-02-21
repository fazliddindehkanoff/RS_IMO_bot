"""Utility functions for admin panel."""
import asyncio
import logging
import time
import threading
from pathlib import Path
from django.conf import settings
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile

logger = logging.getLogger(__name__)

# Global event loop and reused bot for background tasks
_background_loop = None
_background_thread = None
_shared_bot = None


def get_background_loop():
    """Get or create background event loop for sending messages."""
    global _background_loop, _background_thread
    
    if _background_loop is None or _background_loop.is_closed():
        def run_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()
        
        _background_loop = asyncio.new_event_loop()
        _background_thread = threading.Thread(
            target=run_loop,
            args=(_background_loop,),
            daemon=True
        )
        _background_thread.start()
        logger.info("Started background event loop for message sending")
    
    return _background_loop


def _get_bot():
    """Get or create shared Bot instance (used inside background loop). Reusing one bot avoids repeated connection setup and timeouts."""
    global _shared_bot
    if _shared_bot is None:
        _shared_bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
    return _shared_bot


def send_test_assignment_message(telegram_id: int, test, with_start_button: bool = False, language_options=None):
    """
    Send test assignment message to user via Telegram.

    Args:
        telegram_id: User's Telegram ID
        test: Test model instance
        with_start_button: If True, attach inline "Boshlash" button to start the test
    """
    from bot.keyboards import get_start_test_keyboard, get_language_selection_keyboard
    from admin_panel.models import Test

    # Pre-fetch all Django ORM data before entering async context
    test_title = test.title
    test_grade_display = test.get_grade_display()
    test_duration = test.duration_minutes
    test_questions_count = test.get_questions_count()
    test_id = test.id

    async def _send_message():
        bot = _get_bot()
        if language_options:
            language_labels = dict(Test.LANGUAGE_CHOICES)
            message_text = (
                f"📝 <b>Yangi test yuborildi!</b>\n\n"
                f"<b>Test:</b> {test_title}\n"
                f"<b>Sinf:</b> {test_grade_display}\n"
                f"<b>Davomiyligi:</b> {test_duration} daqiqa\n"
                f"<b>Savollar soni:</b> {test_questions_count}\n\n"
                "Iltimos, test tilini tanlang."
            )
            reply_markup = get_language_selection_keyboard(language_options, language_labels)
        else:
            message_text = (
                f"📝 <b>Yangi test yuborildi!</b>\n\n"
                f"<b>Test:</b> {test_title}\n"
                f"<b>Sinf:</b> {test_grade_display}\n"
                f"<b>Davomiyligi:</b> {test_duration} daqiqa\n"
                f"<b>Savollar soni:</b> {test_questions_count}\n\n"
                "Testni boshlash uchun quyidagi <b>Boshlash</b> tugmasini bosing."
            )
            reply_markup = get_start_test_keyboard(test_id=test_id) if with_start_button else None
        await bot.send_message(
            chat_id=telegram_id,
            text=message_text,
            reply_markup=reply_markup,
        )
        logger.info("Test assignment message sent to %s", telegram_id)

    loop = get_background_loop()
    future = asyncio.run_coroutine_threadsafe(_send_message(), loop)
    try:
        future.result(timeout=60)
    except TimeoutError:
        logger.error(
            "Timeout sending test assignment to %s (60s). Check BOT_TOKEN and network.",
            telegram_id,
        )
        raise TimeoutError(
            f"Telegram xabar yuborish 60 soniyadan oshdi (ID: {telegram_id}). "
            "Bot token va internet ulanishini tekshiring."
        )
    except Exception as e:
        logger.error("Error sending test assignment message to %s: %s", telegram_id, e)
        raise


def send_certificate_message(telegram_id: int, certificate_image_path: str, delay_seconds: float = 1.0):
    """
    Send certificate image to user via Telegram with rate limiting.
    
    Args:
        telegram_id: User's Telegram ID
        certificate_image_path: Path to certificate image file (relative to MEDIA_ROOT or absolute)
        delay_seconds: Delay before sending (for rate limiting)
    """
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

    async def _send_certificate():
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)
        bot = _get_bot()
        file = FSInputFile(str(image_path))
        
        if image_path.suffix.lower() == '.pdf':
            await bot.send_document(
                chat_id=telegram_id,
                document=file,
                caption=message_text,
            )
        else:
            await bot.send_photo(
                chat_id=telegram_id,
                photo=file,
                caption=message_text,
            )
        logger.info("Certificate sent to %s", telegram_id)

    loop = get_background_loop()
    future = asyncio.run_coroutine_threadsafe(_send_certificate(), loop)
    try:
        future.result(timeout=60)
    except TimeoutError:
        logger.error(
            "Timeout sending certificate to %s (60s). Check BOT_TOKEN and network.",
            telegram_id,
        )
        raise TimeoutError(
            f"Telegram sertifikat yuborish 60 soniyadan oshdi (ID: {telegram_id}). "
            "Bot token va internet ulanishini tekshiring."
        )
    except Exception as e:
        logger.error("Error sending certificate message to %s: %s", telegram_id, e)
        raise


def send_referral_notification(telegram_id: int, referred_user_name: str, points_earned: int = 5):
    """
    Notify referrer that someone signed up via their link and they earned points.

    Args:
        telegram_id: Referrer's Telegram ID
        referred_user_name: Display name of the user who just registered
        points_earned: Points earned (default 5)
    """
    message_text = (
        f"🎉 <b>Tabriklaymiz!</b>\n\n"
        f"Sizning havolangiz orqali <b>{referred_user_name}</b> ro'yxatdan o'tdi.\n\n"
        f"Siz <b>{points_earned}</b> ball qo'lga kiritdingiz!"
    )

    async def _send_message():
        bot = _get_bot()
        await bot.send_message(
            chat_id=telegram_id,
            text=message_text,
        )
        logger.info("Referral notification sent to %s", telegram_id)

    loop = get_background_loop()
    future = asyncio.run_coroutine_threadsafe(_send_message(), loop)
    try:
        future.result(timeout=30)
    except TimeoutError:
        logger.error("Timeout sending referral notification to %s", telegram_id)
    except Exception as e:
        logger.error("Error sending referral notification to %s: %s", telegram_id, e)
