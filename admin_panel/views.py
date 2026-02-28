"""Webhook view for Telegram bot."""
import hashlib
import hmac
import json
import asyncio
import logging
import os
import threading
import time as _time
from urllib.parse import parse_qs, unquote

import requests
from django.db import transaction, IntegrityError
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView
from django.conf import settings
from django.utils import timezone

from exam_bot_admin.webhook import bot, dp
from admin_panel.models import Student, Parent, Teacher, BotState, Test, TestAttempt, TestQuestion, TestAnswer
from bot.constants import SUCCESS_MESSAGE, OTHER_GRADE_SUCCESS_MESSAGE, PROMO_AFTER_REG_TEXT, OTHER_GRADE_PROMO_MESSAGE, CONTEST_PROMO_REPLY

logger = logging.getLogger(__name__)


def _normalize_phone(raw_phone: str) -> str:
    """Normalize phone input to digits with optional leading +."""
    if not raw_phone:
        return ""
    raw_phone = raw_phone.strip()
    prefix = "+" if raw_phone.startswith("+") else ""
    digits = "".join(ch for ch in raw_phone if ch.isdigit())
    if not digits:
        return ""
    return f"{prefix}{digits}" if prefix else digits


def validate_telegram_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> dict | None:
    """Validate Telegram WebApp initData using HMAC-SHA256.
    Returns the parsed data dict (with 'user' as a parsed JSON object) on success, None on failure.
    See: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data or not bot_token:
        return None
    try:
        parsed = parse_qs(init_data, keep_blank_values=True)
        received_hash = parsed.pop("hash", [None])[0]
        if not received_hash:
            return None

        data_check_pairs = []
        for key in sorted(parsed):
            val = parsed[key][0]
            data_check_pairs.append(f"{key}={val}")
        data_check_string = "\n".join(data_check_pairs)

        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(computed_hash, received_hash):
            return None

        auth_date = parsed.get("auth_date", [None])[0]
        if auth_date and max_age_seconds:
            if _time.time() - int(auth_date) > max_age_seconds:
                return None

        result = {k: v[0] for k, v in parsed.items()}
        if "user" in result:
            result["user"] = json.loads(result["user"])
        return result
    except Exception as e:
        logger.warning("initData validation failed: %s", e)
        return None

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
    phone_number = _normalize_phone((data.get("phone_number") or ""))
    if len(first_name) < 2 or len(last_name) < 2 or len(phone_number) < 9 or len(phone_number) > 20:
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
    guardian_phone = _normalize_phone((data.get("guardian_phone") or "")) or None
    if guardian_phone and len(guardian_phone) > 20:
        guardian_phone = None
    teacher_name = (data.get("teacher_name") or "").strip() or None
    teacher_phone = _normalize_phone((data.get("teacher_phone") or "")) or None
    if teacher_phone and len(teacher_phone) > 20:
        teacher_phone = None

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
def reg_app_user_info_view(request):
    """Return prefilled user data (phone) after validating Telegram initData."""
    if request.method == "OPTIONS":
        return _add_cors_headers(HttpResponse(status=200))

    try:
        body = json.loads(request.body)
    except (ValueError, TypeError):
        resp = JsonResponse({"ok": False}, status=400)
        return _add_cors_headers(resp)

    init_data = body.get("init_data", "")
    validated = validate_telegram_init_data(init_data, settings.BOT_TOKEN)
    if not validated or "user" not in validated:
        resp = JsonResponse({"ok": False, "error": "auth_failed"}, status=403)
        return _add_cors_headers(resp)

    telegram_id = validated["user"].get("id")
    if not telegram_id:
        resp = JsonResponse({"ok": False, "error": "no_user_id"}, status=400)
        return _add_cors_headers(resp)

    phone = ""
    phone_owner = ""
    is_registered = False
    student_data = {}
    
    def strip_phone_prefix(raw_phone):
        """Strip +998 prefix from phone number."""
        raw = (raw_phone or "").strip()
        if raw.startswith("+998"):
            return raw[4:]
        elif raw.startswith("998") and len(raw) > 9:
            return raw[3:]
        return raw
    
    try:
        student = Student.objects.select_related('parent', 'teacher').get(telegram_id=int(telegram_id))
        phone = strip_phone_prefix(student.phone_number)
        phone_owner = student.phone_owner or ""
        is_registered = student.is_fully_registered
        
        # Prepare full student data for pre-filling form
        student_data = {
            "first_name": student.first_name or "",
            "last_name": student.last_name or "",
            "phone_number": phone,
            "region": student.region or "",
            "district": student.district or "",
            "grade": student.grade if student.grade is not None else "",
            "school_name": student.school_name or "",
            "document_number": student.document_number or "",
        }
        
        # Add parent/guardian info if exists
        if hasattr(student, 'parent') and student.parent:
            parent = student.parent
            student_data["guardian_name"] = parent.full_name or ""
            student_data["guardian_phone"] = strip_phone_prefix(parent.phone_number)
        
        # Add teacher info if exists
        if hasattr(student, 'teacher') and student.teacher:
            teacher = student.teacher
            student_data["teacher_name"] = teacher.full_name or ""
            student_data["teacher_phone"] = strip_phone_prefix(teacher.phone_number)
            
    except (Student.DoesNotExist, ValueError, TypeError):
        pass

    resp = JsonResponse({
        "ok": True,
        "phone": phone,
        "phone_owner": phone_owner,
        "user_id": telegram_id,
        "is_registered": is_registered,
        "student_data": student_data,
    })
    return _add_cors_headers(resp)


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

    # Prefer secure identification via Telegram initData
    init_data = data.get("init_data", "")
    validated = validate_telegram_init_data(init_data, settings.BOT_TOKEN) if init_data else None

    if validated and "user" in validated:
        telegram_id = int(validated["user"]["id"])
        username = validated["user"].get("username") or (data.get("username") or "").strip() or None
    else:
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
                [{"text": "\U0001f464 Mening ma'lumotlarim"}],
            ],
            "resize_keyboard": True,
            "one_time_keyboard": False,
        }
    else:
        reply_markup = {
            "keyboard": [
                [{"text": "\U0001f3c6 Konkursda qatnashish"}],
                [{"text": "\U0001f4dd 1-bosqich sinov testini yechish: 1-mart"}],
                [{"text": "\u270f\ufe0f Taklif va shikoyatlar"}, {"text": "\U0001f525 Konkursdagi ballarim"}],
                [{"text": "\U0001f3c6 Reyting"}],
                [{"text": "\U0001f464 Mening ma'lumotlarim"}],
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
    """Serves the registration Mini App (Web App) opened from Telegram menu button."""
    template_name = "reg_app.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["logo_url"] = "/media/rmo_logo.jpg"
        ctx["reg_app_submit_url"] = "/reg-app/submit/"
        return ctx

class TestAppView(TemplateView):
    """Serves the test Mini App (Web App) opened from Telegram menu button."""
    template_name = "test_app.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["test_app_questions_url"] = "/test-app/questions/"
        ctx["test_app_submit_url"] = "/test-app/submit/"
        return ctx

@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def test_app_questions_view(request):
    """Return questions for the user's active test."""
    if request.method == "OPTIONS":
        return _add_cors_headers(HttpResponse(status=200))

    try:
        body = json.loads(request.body)
    except (ValueError, TypeError):
        return _add_cors_headers(JsonResponse({"ok": False}, status=400))

    init_data = body.get("init_data", "")
    fallback_uid = body.get("fallback_uid")
    start_test = body.get("start_test", False)
    
    telegram_id = None
    if init_data:
        validated = validate_telegram_init_data(init_data, settings.BOT_TOKEN)
        if validated and "user" in validated:
            telegram_id = validated["user"].get("id")
            
    if not telegram_id and fallback_uid:
        telegram_id = fallback_uid
        
    if not telegram_id:
        return _add_cors_headers(JsonResponse({"ok": False, "error": "auth_failed"}, status=403))

    try:
        student = Student.objects.get(telegram_id=int(telegram_id))
    except (Student.DoesNotExist, ValueError):
        return _add_cors_headers(JsonResponse({"ok": False, "error_text": "O'quvchi topilmadi. Ro'yxatdan o'ting!"}, status=404))

    # Find active test for their grade
    test = Test.objects.filter(grade=student.grade, is_active=True).first()
    if not test:
        return _add_cors_headers(JsonResponse({"ok": False, "error_text": "Sizning sinfingiz uchun faol test topilmadi."}, status=404))

    # Check time window
    now = timezone.now()
    if test.starts_at and now < test.starts_at:
        return _add_cors_headers(JsonResponse({
            "ok": False,
            "error_text": f"Test {test.starts_at.strftime('%d.%m.%Y %H:%M')} da boshlanadi."
        }, status=403))
    if hasattr(test, 'ends_at') and test.ends_at and now > test.ends_at:
        return _add_cors_headers(JsonResponse({
            "ok": False,
            "error_text": f"Test {test.ends_at.strftime('%d.%m.%Y %H:%M')} da yakunlandi."
        }, status=403))
    if test.finish_at and now > test.finish_at:
        return _add_cors_headers(JsonResponse({"ok": False, "error_text": "Test vaqti tugadi."}, status=403))

    # Attempt tracking
    attempt = TestAttempt.objects.filter(student=student, test=test).order_by('-created_at').first()
    if attempt and attempt.status == 'SUBMITTED_FINAL':
        return _add_cors_headers(JsonResponse({"ok": True, "status": "SUBMITTED_FINAL"}))
    
    if not attempt or attempt.status == 'PENDING':
        from datetime import timedelta
        if not attempt:
            attempt = TestAttempt.objects.create(student=student, test=test, status='PENDING')
        
        if not start_test:
            # Tell frontend we are pending so it can show the start screen
            questions_count = TestQuestion.objects.filter(test=test).count()
            return _add_cors_headers(JsonResponse({
                "ok": True, 
                "status": "PENDING",
                "test_title": test.title,
                "duration_minutes": test.duration_minutes,
                "questions_count": questions_count
            }))
            
        # If start_test is sent, start the timer
        attempt.status = 'IN_PROGRESS'
        attempt.started_at = now
        attempt.expires_at = now + timedelta(minutes=test.duration_minutes)
        attempt.save()

    # If active but expired, force submit
    if attempt.expires_at and now > attempt.expires_at:
        attempt.status = 'SUBMITTED_FINAL'
        attempt.submitted_at = now
        attempt.save()
        return _add_cors_headers(JsonResponse({"ok": True, "status": "SUBMITTED_FINAL"}))

    questions_qs = TestQuestion.objects.filter(test=test).order_by('question_number')
    existing_answers = {a.question_id: a.answer_choice for a in TestAnswer.objects.filter(attempt=attempt)}
    
    questions_data = []
    for q in questions_qs:
        options = {
            "A": q.option_a or "A",
            "B": q.option_b or "B",
            "C": q.option_c or "C",
            "D": q.option_d or "D",
        }
        
        q_data = {
            "id": q.id,
            "text": q.text,
            "options": options,
            "current_answer": existing_answers.get(q.id)
        }
        if q.image:
            q_data["image_url"] = request.build_absolute_uri(q.image.url)
        questions_data.append(q_data)

    resp = JsonResponse({
        "ok": True,
        "test_title": test.title,
        "expires_at": int(attempt.expires_at.timestamp()) if attempt.expires_at else None,
        "questions": questions_data
    })
    return _add_cors_headers(resp)


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def test_app_submit_view(request):
    """Accept submitted answers, calculate score, and send Telegram success message."""
    if request.method == "OPTIONS":
        return _add_cors_headers(HttpResponse(status=200))

    try:
        body = json.loads(request.body)
    except (ValueError, TypeError):
        return _add_cors_headers(JsonResponse({"ok": False, "error": "invalid_json"}, status=400))

    init_data = body.get("init_data", "")
    fallback_uid = body.get("fallback_uid")
    answers_data = body.get("answers", {})

    telegram_id = None
    if init_data:
        validated = validate_telegram_init_data(init_data, settings.BOT_TOKEN)
        if validated and "user" in validated:
            telegram_id = validated["user"].get("id")

    if not telegram_id and fallback_uid:
        telegram_id = fallback_uid

    if not telegram_id:
        return _add_cors_headers(JsonResponse({"ok": False, "error": "auth_failed"}, status=403))

    try:
        student = Student.objects.get(telegram_id=int(telegram_id))
    except Student.DoesNotExist:
        return _add_cors_headers(JsonResponse({"ok": False, "error_text": "O'quvchi topilmadi"}, status=404))

    test = Test.objects.filter(grade=student.grade, is_active=True).first()
    if not test:
        return _add_cors_headers(JsonResponse({"ok": False, "error_text": "Faol test topilmadi"}, status=404))

    attempt = TestAttempt.objects.filter(student=student, test=test).order_by('-created_at').first()
    if not attempt or attempt.status == 'SUBMITTED_FINAL':
        return _add_cors_headers(JsonResponse({"ok": False, "error_text": "Test allaqachon topshirilgan"}, status=400))

    with transaction.atomic():
        questions = TestQuestion.objects.filter(test=test)
        question_map = {str(q.id): q for q in questions}
        
        for q_id_str, answer_choice in answers_data.items():
            question = question_map.get(q_id_str)
            if question and answer_choice:
                TestAnswer.objects.update_or_create(
                    attempt=attempt,
                    question=question,
                    defaults={
                        'answer_choice': answer_choice,
                        'is_correct': (answer_choice == question.correct_answer),
                        'points_earned': question.ball_weight if (answer_choice == question.correct_answer) else 0.0,
                    }
                )

        # Calculate final score
        all_answers = TestAnswer.objects.filter(attempt=attempt).select_related('question')
        total_points = sum(q.ball_weight for q in questions)
        earned_points = sum(a.points_earned for a in all_answers)
        score = (earned_points / total_points * 100) if total_points > 0 else 0

        attempt.status = 'SUBMITTED_FINAL'
        attempt.submitted_at = timezone.now()
        attempt.total_points = total_points
        attempt.earned_points = earned_points
        attempt.score = score
        attempt.save()

    # Send Success message
    from bot.keyboards import get_main_menu_keyboard
    success_text = "✅ Test muvaffaqiyatli topshirildi!\n\n🏆 Kanalimizda umumiy natijalarni tez kunda e'lon qilamiz, kuzatishda davom eting:\n\n@rs_olimpiada"
    is_other_grade = (student.grade == 0)
    reply_markup = get_main_menu_keyboard(other_grade=is_other_grade, telegram_id=telegram_id)
    
    # We serialize the reply markup correctly for Telegram API
    # ReplyKeyboardMarkup -> dict
    if hasattr(reply_markup, "model_dump"):
        rm_dict = reply_markup.model_dump(exclude_none=True)
    else:
        rm_dict = dict(reply_markup)

    _send_telegram_message(telegram_id, success_text, reply_markup=rm_dict)

    return _add_cors_headers(JsonResponse({"ok": True}))
