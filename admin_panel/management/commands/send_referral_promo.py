"""Django management command to send referral promo text to a user."""
import asyncio
import logging

from aiogram.types import LinkPreviewOptions
from django.core.management.base import BaseCommand

from bot.constants import REFERRAL_ONLY_PROMO_TEXT
from bot.keyboards import get_post_reg_promo_keyboard
from exam_bot_admin.webhook import bot

logger = logging.getLogger(__name__)

TARGET_USER_ID = 1535815443


class Command(BaseCommand):
    help = "Send referral promo (REFERRAL_ONLY_PROMO_TEXT) to a Telegram user"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user-id",
            type=int,
            default=TARGET_USER_ID,
            help=f"Telegram user ID to send to (default: {TARGET_USER_ID})",
        )

    def handle(self, *args, **options):
        chat_id = options["user_id"]
        self.stdout.write(f"Sending referral promo to user {chat_id}...")

        async def send():
            try:
                await bot.send_message(
                    chat_id,
                    REFERRAL_ONLY_PROMO_TEXT,
                    reply_markup=get_post_reg_promo_keyboard(),
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Referral promo sent to {chat_id}")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Failed to send: {e}")
                )
                raise
            finally:
                await bot.session.close()

        asyncio.run(send())
