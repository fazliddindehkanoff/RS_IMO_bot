"""Django management command to set up Telegram webhook."""
import asyncio
import logging
from django.core.management.base import BaseCommand
from django.conf import settings

from exam_bot_admin.webhook import bot

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Set up Telegram webhook"

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            type=str,
            help="Webhook URL (defaults to WEBHOOK_URL from settings)",
        )
        parser.add_argument(
            "--secret-token",
            type=str,
            help="Webhook secret token (optional)",
        )

    def handle(self, *args, **options):
        webhook_url = options.get("url") or settings.WEBHOOK_URL
        secret_token = options.get("secret_token") or settings.WEBHOOK_SECRET

        self.stdout.write(f"Setting up webhook at: {webhook_url}")

        async def setup():
            try:
                # Set webhook
                await bot.set_webhook(
                    url=webhook_url,
                    secret_token=secret_token if secret_token else None,
                )
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Webhook set successfully at {webhook_url}")
                )

                # Get webhook info
                webhook_info = await bot.get_webhook_info()
                self.stdout.write(f"Webhook info: {webhook_info}")

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Error setting webhook: {e}")
                )
                raise

        asyncio.run(setup())

