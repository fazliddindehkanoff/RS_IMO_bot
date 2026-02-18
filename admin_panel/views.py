"""Webhook view for Telegram bot."""
import json
import asyncio
import logging
import os
import threading
import requests
from django.db import transaction, IntegrityError
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView
from django.conf import settings

from exam_bot_admin.webhook import bot, dp
from admin_panel.models import Student, Parent, Teacher, BotState
from bot.constants import SUCCESS_MESSAGE, OTHER_GRADE_SUCCESS_MESSAGE, PROMO_AFTER_REG_TEXT, OTHER_GRADE_PROMO_MESSAGE, CONTEST_PROMO_REPLY

logger = logging.getLogger(__name__)

# Global event loop running in background thread
_background_loop = None
_background_thread = None


def get_background_loop():
    """Get or create background event loop for processing updates."""
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
        logger.info("Started background event loop for webhook processing")
    
    return _background_loop


@csrf_exempt
@require_http_methods(["POST"])
def webhook_view(request):
    """Handle Telegram webhook updates."""
    try:
        # Parse update from request body
        update_json = json.loads(request.body)
        update_id = update_json.get('update_id', 'unknown')
        logger.debug(f"Received update: {update_id}")

        # Get background loop and schedule update processing
        loop = get_background_loop()
        asyncio.run_coroutine_threadsafe(
            process_update(update_json),
            loop
        )

        # Return 200 OK immediately (Telegram expects quick response)
        return HttpResponse(status=200)

    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook request")
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


async def process_update(update_json):
    """Process a Telegram update."""
    try:
        from aiogram.types import Update

        update = Update(**update_json)
        await dp.feed_update(bot, update)
        logger.debug(f"Processed update {update.update_id}")
    except Exception as e:
        logger.error(f"Error processing update: {e}", exc_info=True)


def _save_reg_app_data(telegram_id: int, username: str, data: dict) -> str | None:
    """Save Web App form data to DB. Returns None on success, error message on failure."""
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    phone_number = (data.get("phone_number") or "").strip()
    if len(first_name) < 2 or len(last_name) < 2 or len(phone_number) < 9:
        return "invalid_data"
    region = (data.get("region") or "").strip() or None
    district = (data.get("district") or "").strip() or None
    grade_raw = data.get("grade")
    grade = None
    if grade_raw is not None:
        if str(grade_raw) == 'other':
            grade = 0
        else:
            try:
                g = int(grade_raw)
                if g in (0, 5, 6, 7, 8):
                    grade = g
            except (TypeError, ValueError):
                pass
    school_name = (data.get("school_name") or "").strip() or None
    document_number = (data.get("document_number") or "").strip()
    document_number = document_number.upper() if document_number else None
    guardian_name = (data.get("guardian_name") or "").strip() or None
    guardian_phone = (data.get("guardian_phone") or "").strip() or None
    teacher_name = (data.get("teacher_name") or "").strip() or None
    teacher_phone = (data.get("teacher_phone") or "").strip() or None

    try:
        with transaction.atomic():
            student, _ = Student.objects.get_or_create(
                telegram_id=telegram_id,
                defaults={"username": username, "first_name": "", "is_active": True, "referral_code": str(telegram_id)},
            )
            if not student.referral_code:
                student.referral_code = str(telegram_id)
            student.username = username or student.username
            student.first_name = first_name
            student.last_name = last_name
            student.phone_number = phone_number
            student.region = region
            student.district = district
            student.grade = grade
            student.school_name = school_name
            student.document_number = document_number
            student.registered_from_web = True
            student.save()

            if guardian_name:
                parent, _ = Parent.objects.get_or_create(
                    student=student,
                    defaults={"full_name": guardian_name, "phone_number": guardian_phone},
                )
                parent.full_name = guardian_name
                parent.phone_number = guardian_phone or parent.phone_number
                parent.save()

            if teacher_name:
                teacher, _ = Teacher.objects.get_or_create(
                    student=student,
                    defaults={"full_name": teacher_name, "phone_number": teacher_phone},
                )
                teacher.full_name = teacher_name
                teacher.phone_number = teacher_phone or teacher.phone_number
                teacher.save()

        BotState.objects.filter(telegram_id=telegram_id).delete()
        return None
    except IntegrityError as e:
        if "document_number" in str(e).lower() or "unique" in str(e).lower():
            return "duplicate_document"
        return "db_error"


def _send_telegram_message(chat_id: int, text: str, reply_markup: dict | None = None) -> bool:
    """Send a Telegram message via Bot API. Returns True on success."""
    token = getattr(settings, "BOT_TOKEN", None)
    if not token:
        logger.warning("BOT_TOKEN not set, cannot send Telegram message")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        logger.exception("Failed to send Telegram message: %s", e)
        return False


def _add_cors_headers(response):
    """Add CORS headers so Telegram WebView / cross-origin fetch can reach the API."""
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response["Access-Control-Allow-Headers"] = "Content-Type"
    response["Access-Control-Max-Age"] = "86400"
    return response


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def reg_app_submit_view(request):
    """Accept Web App form POST, save data, send success + follow-up messages with 3 inline buttons to user."""
    if request.method == "OPTIONS":
        response = HttpResponse(status=200)
        return _add_cors_headers(response)

    try:
        data = json.loads(request.body)
    except (ValueError, TypeError):
        response = JsonResponse({"ok": False, "error": "invalid_json"}, status=400)
        return _add_cors_headers(response)

    user_id = data.get("user_id")
    if user_id is None:
        response = JsonResponse({"ok": False, "error": "missing_user_id"}, status=400)
        return _add_cors_headers(response)
    try:
        telegram_id = int(user_id)
    except (TypeError, ValueError):
        response = JsonResponse({"ok": False, "error": "invalid_user_id"}, status=400)
        return _add_cors_headers(response)

    username = (data.get("username") or "").strip() or None
    err = _save_reg_app_data(telegram_id, username, data)
    if err == "invalid_data":
        response = JsonResponse({"ok": False, "error": "invalid_data"}, status=400)
        return _add_cors_headers(response)
    if err == "duplicate_document":
        response = JsonResponse({"ok": False, "error": "duplicate_document"}, status=409)
        return _add_cors_headers(response)
    if err == "db_error":
        response = JsonResponse({"ok": False, "error": "db_error"}, status=500)
        return _add_cors_headers(response)

    # Determine if user selected "other" grade
    grade_raw = data.get("grade")
    is_other_grade = (str(grade_raw) == 'other' or str(grade_raw) == '0')

    # Send SUCCESS_MESSAGE with Reply keyboard (main menu buttons)
    if is_other_grade:
        reply_markup = {
            "keyboard": [
                [{"text": "\U0001f3c6 Konkursda qatnashish"}],
                [{"text": "\u270f\ufe0f Taklif va shikoyatlar"}, {"text": "\U0001f525 Konkursdagi ballarim"}],
                [{"text": "\U0001f3c6 Reyting"}],
            ],
            "resize_keyboard": True,
            "one_time_keyboard": False,
        }
    else:
        reply_markup = {
            "keyboard": [
                [{"text": "\U0001f3c6 Konkursda qatnashish"}],
                [{"text": "\U0001f4dd 1-bosqich testini yechish: 22-fevral"}],
                [{"text": "\u270f\ufe0f Taklif va shikoyatlar"}, {"text": "\U0001f525 Konkursdagi ballarim"}],
                [{"text": "\U0001f3c6 Reyting"}],
            ],
            "resize_keyboard": True,
            "one_time_keyboard": False,
        }
    success_text = OTHER_GRADE_SUCCESS_MESSAGE if is_other_grade else SUCCESS_MESSAGE
    ok1 = _send_telegram_message(telegram_id, success_text, reply_markup=reply_markup)
    if not ok1:
        logger.warning("Failed to send success message to %s", telegram_id)

    # Schedule 30-second delayed promotional message
    timer = threading.Timer(30, _send_delayed_promo_sync, args=[telegram_id, is_other_grade])
    timer.daemon = True
    timer.start()

    response = JsonResponse({"ok": True})
    return _add_cors_headers(response)


def _send_telegram_photo(chat_id: int, photo_path: str, caption: str) -> dict | None:
    """Send a photo via Bot API. Returns the sent message dict on success, None on failure."""
    token = getattr(settings, "BOT_TOKEN", None)
    if not token:
        return None
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    try:
        with open(photo_path, 'rb') as f:
            r = requests.post(url, data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}, files={"photo": f}, timeout=15)
        if r.status_code == 200:
            return r.json().get("result")
    except Exception as e:
        logger.exception("Failed to send Telegram photo: %s", e)
    return None


def _get_bot_username() -> str:
    """Get bot username via getMe API."""
    token = getattr(settings, "BOT_TOKEN", None)
    if not token:
        return ""
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
        if r.status_code == 200:
            return r.json().get("result", {}).get("username", "")
    except Exception:
        pass
    return ""


def _send_delayed_promo_sync(telegram_id: int, is_other_grade: bool = False):
    """Send promotional message (called 30s after registration via threading.Timer)."""
    try:
        if is_other_grade:
            student = Student.objects.filter(telegram_id=telegram_id).first()
            if not student:
                return
            bot_username = _get_bot_username()
            ref_code = student.referral_code or str(telegram_id)
            referral_link = f"https://t.me/{bot_username}?start={ref_code}" if bot_username else ""
            promo_text = OTHER_GRADE_PROMO_MESSAGE.format(referral_link=referral_link)

            photo_path = os.path.join(settings.MEDIA_ROOT, "rmo_logo.jpg")
            sent = None
            if os.path.exists(photo_path):
                sent = _send_telegram_photo(telegram_id, photo_path, promo_text)
            if not sent:
                _send_telegram_message(telegram_id, promo_text)
                return
            sent_msg_id = sent.get("message_id")
            if sent_msg_id:
                token = getattr(settings, "BOT_TOKEN", None)
                if token:
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    payload = {
                        "chat_id": telegram_id,
                        "text": CONTEST_PROMO_REPLY,
                        "parse_mode": "HTML",
                        "reply_to_message_id": sent_msg_id,
                    }
                    requests.post(url, json=payload, timeout=10)
        else:
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "\U0001f3c6 Konkursda qatnashish", "callback_data": "contest_participate_promo"}]
                ]
            }
            _send_telegram_message(telegram_id, PROMO_AFTER_REG_TEXT, reply_markup=reply_markup)
    except Exception as e:
        logger.error("Failed to send delayed promo to %s: %s", telegram_id, e)


class RegAppView(TemplateView):
    """Serves the registration Mini App (Web App) opened from /reg inline button."""
    template_name = "reg_app.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["logo_url"] = "/media/rmo_logo.jpg"
        ctx["reg_app_submit_url"] = "/reg-app/submit/"
        user_id = self.request.GET.get("user_id", "")
        ctx["user_id"] = user_id
        phone = ""
        if user_id:
            try:
                student = Student.objects.get(telegram_id=int(user_id))
                raw = student.phone_number or ""
                # Strip +998 prefix — form shows only the 9 digits after the prefix
                raw = raw.strip()
                if raw.startswith("+998"):
                    phone = raw[4:]
                elif raw.startswith("998") and len(raw) > 9:
                    phone = raw[3:]
                else:
                    phone = raw
            except (Student.DoesNotExist, ValueError, TypeError):
                pass
        ctx["phone_number"] = phone
        return ctx
