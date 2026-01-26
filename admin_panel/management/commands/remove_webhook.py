"""Django management command to remove Telegram webhook."""
import asyncio
import logging
from django.core.management.base import BaseCommand

from exam_bot_admin.webhook import bot

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Remove Telegram webhook (switch back to polling)"

    def handle(self, *args, **options):
        self.stdout.write("Removing webhook...")

        async def remove():
            try:
                await bot.delete_webhook()
                self.stdout.write(
                    self.style.SUCCESS("✅ Webhook removed successfully")
                )

                # Get webhook info
                webhook_info = await bot.get_webhook_info()
                self.stdout.write(f"Webhook info: {webhook_info}")

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Error removing webhook: {e}")
                )
                raise

        asyncio.run(remove())

