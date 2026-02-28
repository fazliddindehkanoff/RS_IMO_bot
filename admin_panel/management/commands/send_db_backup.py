"""Django management command to send a database backup to all admin users via the bot."""
import asyncio
import io
import json
import logging
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core import serializers

logger = logging.getLogger(__name__)

# Tables to include in the backup (app_label.ModelName format)
BACKUP_MODELS = [
    "admin_panel.Student",
    "admin_panel.Parent",
    "admin_panel.Teacher",
    "admin_panel.Partner",
    "admin_panel.Referral",
    "admin_panel.RegistrationSource",
    "admin_panel.Test",
    "admin_panel.TestQuestion",
    "admin_panel.TestAttempt",
    "admin_panel.TestAnswer",
    "admin_panel.MandatoryChannel",
]


def _get_model_class(model_path: str):
    """Import and return a model class by 'app_label.ModelName'."""
    from django.apps import apps
    app_label, model_name = model_path.split(".")
    return apps.get_model(app_label, model_name)


def generate_backup_json() -> tuple[bytes, dict]:
    """
    Serialize all required tables to a JSON payload.
    Returns (json_bytes, stats_dict).
    """
    all_objects = []
    stats = {}

    for model_path in BACKUP_MODELS:
        try:
            model = _get_model_class(model_path)
            qs = model.objects.all()
            count = qs.count()
            stats[model_path] = count
            # Serialize this queryset and extend the list
            serialized = serializers.serialize("python", qs)
            all_objects.extend(serialized)
        except Exception as e:
            logger.warning(f"Could not back up {model_path}: {e}")
            stats[model_path] = f"ERROR: {e}"

    json_bytes = json.dumps(all_objects, ensure_ascii=False, indent=2, default=str).encode("utf-8")
    return json_bytes, stats


async def _send_backup_to_admins(json_bytes: bytes, stats: dict):
    """Generate backup JSON and send it to every admin user."""
    from exam_bot_admin.webhook import bot

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"backup_{timestamp}.json"

    # Build stats caption
    total_records = sum(v for v in stats.values() if isinstance(v, int))
    table_lines = "\n".join(
        f"  • {path.split('.')[1]}: {count}"
        for path, count in stats.items()
    )
    caption = (
        f"🗄 <b>Database Backup</b>\n"
        f"📅 {timestamp}\n"
        f"📦 Jami yozuvlar: <b>{total_records}</b>\n\n"
        f"<b>Jadvallar:</b>\n{table_lines}\n\n"
        f"✅ Faylni yuklab oling va kerak bo'lganda qayta yuklash uchun foydalaning."
    )
    
    if len(caption) > 1024:
        table_lines = table_lines[:800] + "\n  • ... (qisqartirildi)"
        caption = (
            f"🗄 <b>Database Backup</b>\n"
            f"📅 {timestamp}\n"
            f"📦 Jami yozuvlar: <b>{total_records}</b>\n\n"
            f"<b>Jadvallar:</b>\n{table_lines}\n\n"
            f"✅ Faylni yuklab oling va..."
        )

    errors = []
    for admin_id in settings.ADMIN_IDS:
        try:
            from aiogram.types import BufferedInputFile
            await bot.send_document(
                chat_id=admin_id,
                document=BufferedInputFile(json_bytes, filename=filename),
                caption=caption,
                parse_mode="HTML",
            )
            logger.info(f"Backup sent to admin {admin_id}")
        except Exception as e:
            logger.error(f"Failed to send backup to admin {admin_id}: {e}")
            errors.append((admin_id, str(e)))

    await bot.session.close()
    return errors


class Command(BaseCommand):
    help = "Generate a JSON backup of the required database tables and send it to all admin users via the bot."

    def handle(self, *args, **options):
        self.stdout.write("📦 Generating database backup...")

        try:
            json_bytes, stats = generate_backup_json()
            errors = asyncio.run(_send_backup_to_admins(json_bytes, stats))

            self.stdout.write("\n📊 Backup stats:")
            for model_path, count in stats.items():
                self.stdout.write(f"  {model_path}: {count}")

            if errors:
                for admin_id, err in errors:
                    self.stdout.write(
                        self.style.ERROR(f"  ❌ Failed to send to {admin_id}: {err}")
                    )
            else:
                self.stdout.write(self.style.SUCCESS("\n✅ Backup sent to all admins successfully."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Backup failed: {e}"))
            raise
