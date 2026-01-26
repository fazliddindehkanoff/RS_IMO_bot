from django.apps import AppConfig
import asyncio
import logging

logger = logging.getLogger(__name__)


class AdminPanelConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "admin_panel"

    def ready(self):
        """Initialize bot when Django is ready."""
        from exam_bot_admin.webhook import init_bot

        # Run async initialization
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if not loop.is_running():
            try:
                loop.run_until_complete(init_bot())
            except Exception as e:
                logger.error(f"Error initializing bot: {e}", exc_info=True)
