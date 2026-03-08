import json
import logging
import os
import asyncio
from datetime import datetime
from pathlib import Path

from aiogram import Router, F
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    FSInputFile, LinkPreviewOptions, Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
)
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import IntegrityError

from bot.constants import (
    GREETING_MESSAGE, REG_GREETING_MESSAGE, REG_BUTTON_LABEL,
    STEP_INITIAL_PHONE, STEP_PHONE_OWNER, SUCCESS_INITIAL_REG,
    PROMO_TEXT, OLYMPIAD_INTRO, OLYMPIAD_DECLINED, REFERRAL_ONLY_PROMO_TEXT,
    STEP_1_ASK_NAME, STEP_2_ASK_SURNAME, STEP_3_ASK_DOB, STEP_4_ASK_METRIKA,
    STEP_5_ASK_REGION, STEP_6_ASK_DISTRICT, STEP_7_ASK_SCHOOL, STEP_8_ASK_GRADE,
    STEP_9_ASK_PHOTO, STEP_10_ASK_ACHIEVEMENTS, STEP_11_ASK_GUARDIAN_NAME,
    STEP_12_ASK_RELATIONSHIP, STEP_13_ASK_GUARDIAN_PHONE, STEP_14_ASK_TEACHER_NAME,
    STEP_15_ASK_TEACHER_PHONE, STEP_16_ASK_SOURCE, STEP_17_CONFIRMATION_HEADER,
    SUCCESS_MESSAGE, OTHER_GRADE_SUCCESS_MESSAGE, PROMO_MESSAGE, PROMO_AFTER_REG_TEXT,
    CONTEST_PROMO_MESSAGE, CONTEST_PROMO_REPLY, OTHER_GRADE_PROMO_MESSAGE,
    ERROR_NAME_LENGTH, ERROR_SURNAME_LENGTH,
    ERROR_DATE_FORMAT, ERROR_INVALID_PHOTO, ERROR_INVALID_FILE, ERROR_INVALID_AGE,
    ERROR_INVALID_PHONE_UZB, ERROR_USE_BUTTONS, ALREADY_REGISTERED,
    REFERRAL_POINTS, REFERRAL_DESC, LEADERBOARD_TITLE,
    LEADERBOARD_EMPTY, LEADERBOARD_USER_RANK, CHECK_SUBS_FAIL, CHECK_SUBS_SUCCESS,
    CHECK_SUBS_START, CHECK_SUBS_CONFIRMED_ANSWER, CHECK_SUBS_NOT_CONFIRMED,
    EDIT_TITLE, EDIT_PROMPT_PREFIX, EDIT_FIELD_SUFFIXES,
    ERROR_NOT_REGISTERED, ERROR_DATE_FORMAT_EDIT, ERROR_INVALID_FILE_OR_SKIP,
    MENU_PROMPT, OTHER_GRADE_MESSAGE, OTHER_GRADE_PROMO_MESSAGE
)
from bot.keyboards import (
    get_grade_keyboard, get_region_keyboard, get_language_keyboard,
    get_main_menu_keyboard, get_confirmation_keyboard, get_edit_fields_keyboard,
    get_skip_keyboard, get_relationship_keyboard, get_source_type_keyboard,
    get_post_reg_promo_keyboard, get_referral_menu_confirm_keyboard, get_phone_keyboard, get_phone_owner_keyboard,
    get_olympiad_participation_keyboard, get_back_reply_keyboard, get_back_keyboard,
)
from bot.services import BotStateService, StudentService, SubscriptionService, TestService, build_channel_keyboard
from bot.states import RegistrationStates
from admin_panel.models import RegistrationSource, Student, Parent, Teacher

logger = logging.getLogger(__name__)
router = Router()

# Initial registration states where we (re)show the welcome video on /start
WELCOME_VIDEO_STATES = frozenset({
    "waiting_for_initial_full_name",
    "waiting_for_initial_phone",
    "waiting_for_phone_owner",
})


async def _send_welcome_video_if_exists(message: Message) -> bool:
    """Send welcome video note if file exists. Retries once on failure. Returns True if sent."""
    media_root = Path(settings.MEDIA_ROOT)
    video_path = media_root / "welcome_video.mp4"
    if not video_path.is_file():
        logger.debug("Welcome video not found at %s", video_path.resolve())
        return False
    for attempt in range(2):
        try:
            await message.answer_video_note(FSInputFile(str(video_path)))
            await asyncio.sleep(0.5)
            return True
        except Exception as e:
            logger.warning(
                "Failed to send welcome video (attempt %s) from %s: %s",
                attempt + 1, video_path.resolve(), e, exc_info=(attempt == 1)
            )
            if attempt == 0:
                await asyncio.sleep(2)
    return False


def _reg_webapp_url_with_user(telegram_id: int, phone: str = "") -> str:
    """Build REG_WEBAPP_URL with user_id and phone query params for the Web App."""
    from urllib.parse import quote
    base = getattr(settings, "REG_WEBAPP_URL", "").strip()
    if not base:
        return ""
    sep = "&" if "?" in base else "?"
    url = f"{base}{sep}user_id={telegram_id}"
    if phone:
        url += f"&phone={quote(phone)}"
    return url


# build_channel_keyboard is imported from bot.services to avoid duplication and circular imports


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


async def _safe_delete_message(message: Message | None, context: str = "") -> bool:
    """Delete a message, ignoring Telegram delete errors."""
    if not message:
        return False
    try:
        await message.delete()
        return True
    except TelegramBadRequest as exc:
        logger.info("Skipping delete for %s: %s", context or "message", exc)
    except Exception as exc:
        logger.warning("Failed to delete %s: %s", context or "message", exc)
    return False


async def _safe_callback_answer(callback: CallbackQuery, *args, **kwargs) -> bool:
    """Answer a callback query, ignoring expired/invalid query errors."""
    try:
        await callback.answer(*args, **kwargs)
        return True
    except TelegramBadRequest as exc:
        logger.info("Skipping callback.answer: %s", exc)
    except Exception as exc:
        logger.warning("Failed callback.answer: %s", exc)
    return False


# All registration state names stored in BotStateService (used for /start resume)
REGISTRATION_STATE_NAMES = {
    "waiting_for_initial_full_name", "waiting_for_initial_phone", "waiting_for_phone_owner",
    "waiting_for_webapp_reg",
    "waiting_for_olympiad_participation",
    "waiting_for_confirmation", "waiting_for_channels",
    "waiting_for_post_reg_promo", "waiting_for_edit_field", "editing_field",
}


async def _restore_state_from_db_middleware(handler, event: Message | CallbackQuery, data: dict):
    """When FSM state is empty, restore from BotState or infer from Student DB so the user is
    navigated back to their current step (e.g. after deployment or lost in-memory state)."""
    state: FSMContext = data.get("state")
    if state is None or not event.from_user:
        return await handler(event, data)
    current = await state.get_state()
    if current is not None:
        return await handler(event, data)

    telegram_id = event.from_user.id
    # 1) Try saved BotState (e.g. same worker had set it)
    state_obj = await BotStateService.get_state(telegram_id)
    if state_obj and state_obj.state in REGISTRATION_STATE_NAMES:
        reg_state = getattr(RegistrationStates, state_obj.state, None)
        if reg_state is not None:
            await state.set_state(reg_state)
            if state_obj.state_data:
                await state.update_data(**state_obj.state_data)
            return await handler(event, data)

    # 2) No BotState: infer from Student (and related) data and restore
    inferred_state, inferred_data = await _infer_registration_state_from_db(telegram_id)
    if inferred_state:
        reg_state = getattr(RegistrationStates, inferred_state, None)
        if reg_state is not None:
            await state.set_state(reg_state)
            if inferred_data:
                await state.update_data(**inferred_data)
            await BotStateService.set_state(telegram_id, inferred_state, inferred_data)
    return await handler(event, data)


router.message.outer_middleware(_restore_state_from_db_middleware)
router.callback_query.outer_middleware(_restore_state_from_db_middleware)


def _build_confirmation_text(student, parent, teacher, source):
    """Build confirmation screen text from student, parent, teacher, source (for resume and save_all_data)."""
    text = "🥳 Nihoyat, eng so'nggi qadam:\n\n"
    text += "📝 Ushbu ma'lumotlarni tasdiqlaysizmi? 👇\n\n"
    text += "<b>📋 O'quvchi ma'lumotlari:</b>\n"
    text += f"• Ism: {student.first_name}\n"
    text += f"• Familiya: {student.last_name or '—'}\n"
    text += f"• Tug'ilgan sana: {student.date_of_birth or '—'}\n"
    text += f"• Metrika: {student.document_number or '—'}\n"
    text += f"• Viloyat: {dict(Student.REGION_CHOICES).get(student.region, '—')}\n"
    text += f"• Tuman/shahar: {student.district or '—'}\n"
    text += f"• Maktab: {student.school_name or '—'}\n"
    text += f"• Sinf: {dict(Student.GRADE_CHOICES).get(student.grade, '—')}\n"
    text += f"• Foto: {'✅ Yuklangan' if student.photo else '❌'}\n"
    text += f"• Yutuqlar: {student.achievements_description or 'Yo\'q'}\n\n"
    text += "<b>👤 Vasiy ma'lumotlari:</b>\n"
    if parent:
        text += f"• Ism: {parent.full_name}\n"
        text += f"• Kimligi: {dict(Parent.RELATIONSHIP_CHOICES).get(parent.relationship, '—')}\n"
        text += f"• Tel: {parent.phone_number or '—'}\n\n"
    else:
        text += "Kiritilmadi\n\n"
    text += "<b>🧑‍🏫 Ustoz ma'lumotlari:</b>\n"
    if teacher:
        text += f"• Ism: {teacher.full_name}\n"
        text += f"• Tel: {teacher.phone_number or '—'}\n\n"
    else:
        text += "Kiritilmadi\n\n"
    text += "<b>📊 Manba:</b>\n"
    if source:
        text += f"• {dict(RegistrationSource.SOURCE_TYPE_CHOICES).get(source.source_type, '—')}\n"
    else:
        text += "Kiritilmadi\n"
    return text


async def _get_continuation_for_state(telegram_id: int, state_name: str, data: dict, bot=None):
    """Return (text, reply_markup) to re-send when user hits /start in the middle of registration. None if not resumable."""
    d = data
    if state_name == "waiting_for_initial_full_name":
        return (GREETING_MESSAGE, None)
    if state_name == "waiting_for_initial_phone":
        return (STEP_INITIAL_PHONE, get_phone_keyboard())
    if state_name == "waiting_for_phone_owner":
        return (STEP_PHONE_OWNER, get_phone_owner_keyboard())
    if state_name == "waiting_for_webapp_reg":
        phone = d.get("initial_phone", "")
        web_app_url = _reg_webapp_url_with_user(telegram_id, phone=phone)
        if not web_app_url:
            return (REG_GREETING_MESSAGE, None)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=REG_BUTTON_LABEL, web_app=WebAppInfo(url=web_app_url))]
        ])
        return (REG_GREETING_MESSAGE, kb)
    if state_name == "waiting_for_olympiad_participation":
        return (PROMO_TEXT, get_olympiad_participation_keyboard())

    if state_name == "waiting_for_confirmation":
        student = await StudentService.get_student(telegram_id)
        parent = await sync_to_async(lambda: getattr(student, "parent", None))()
        try:
            if parent is None:
                parent = await sync_to_async(lambda: student.parent)()
        except Exception:
            parent = None
        teacher = await sync_to_async(lambda: getattr(student, "teacher", None))()
        try:
            if teacher is None:
                teacher = await sync_to_async(lambda: student.teacher)()
        except Exception:
            teacher = None
        source = await sync_to_async(lambda: getattr(student, "registration_source", None))()
        try:
            if source is None:
                source = await sync_to_async(lambda: student.registration_source)()
        except Exception:
            source = None
        text = _build_confirmation_text(student, parent, teacher, source)
        return (text, get_confirmation_keyboard())
    if state_name == "waiting_for_channels":
        if not bot:
            return (CHECK_SUBS_START, None)
        subscription_status = await SubscriptionService.check_subscription(bot, telegram_id)
        if subscription_status["subscribed"]:
            after = d.get("after_channels")
            if after == "full_reg":
                return (SUCCESS_MESSAGE, get_main_menu_keyboard(telegram_id=telegram_id))
            if after == "other_grade":
                return (OTHER_GRADE_PROMO_MESSAGE, get_post_reg_promo_keyboard())
            return (CHECK_SUBS_SUCCESS, None)
        kb = build_channel_keyboard(subscription_status["missing_channels"])
        return (CHECK_SUBS_START, kb)
    if state_name == "waiting_for_post_reg_promo":
        if d.get("school_name"):
            return (OTHER_GRADE_PROMO_MESSAGE, get_post_reg_promo_keyboard())
        return (REFERRAL_ONLY_PROMO_TEXT, get_post_reg_promo_keyboard())
    if state_name in ("waiting_for_edit_field", "editing_field"):
        return (EDIT_TITLE, get_edit_fields_keyboard())

    return (None, None)


async def _award_referral_and_notify(telegram_id: int, bot):
    """Award referral if pending (from DB), notify referrer. Idempotent."""
    referrer_telegram_id, referred_name = await StudentService.award_referral_if_pending(telegram_id)
    if referrer_telegram_id and referred_name:
        try:
            msg = (
                "🎉 <b>Tabriklaymiz!</b>\n\n"
                f"Sizning havolangiz orqali <b>{referred_name}</b> ro'yxatdan o'tdi.\n\n"
                "Siz <b>5</b> ball qo'lga kiritdingiz!"
            )
            await bot.send_message(chat_id=referrer_telegram_id, text=msg, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error("Failed to send referral notification: %s", e)


def _parse_start_referral(message_text: str) -> str | None:
    """Parse /start payload: /start REF_CODE -> return REF_CODE or None."""
    if not message_text or not message_text.strip().startswith("/start"):
        return None
    parts = message_text.strip().split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else None


async def _infer_registration_state_from_db(telegram_id: int):
    """Infer where the user stopped in registration from Student/Parent/Teacher/Source DB.
    Used when FSM state was lost (e.g. after deployment). Returns (state_name, state_data)
    or (None, {}) if fully registered or nothing to resume."""
    student = await StudentService.get_student(telegram_id)
    if not student:
        return None, {}

    # Web App registered users are done — don't push them into 17-step flow
    if student.registered_from_web:
        return None, {}

    # Fully registered: no need to resume (check in sync context to avoid cross-thread DB access)
    if await StudentService.is_fully_registered(telegram_id):
        return None, {}

    try:
        parent = await sync_to_async(lambda: student.parent)()
    except Exception:
        parent = None
    try:
        teacher = await sync_to_async(lambda: student.teacher)()
    except Exception:
        teacher = None
    try:
        source = await sync_to_async(lambda: student.registration_source)()
    except Exception:
        source = None

    def _v(s, attr, default=""):
        val = getattr(s, attr, None) if s else None
        return (val or default).strip() if isinstance(val, str) else (val if val is not None else default)

    # Build state_data from DB so continuation messages and handlers have correct context
    state_data = {
        "initial_full_name": _v(student, "initial_full_name"),
        "initial_phone": _v(student, "phone_number") if getattr(student, "initial_full_name", None) else "",
        "first_name": _v(student, "first_name"),
        "last_name": _v(student, "last_name"),
        "date_of_birth": str(student.date_of_birth) if student.date_of_birth else "",
        "document_number": _v(student, "document_number"),
        "region": _v(student, "region"),
        "district": _v(student, "district"),
        "school_name": _v(student, "school_name"),
        "grade": student.grade if student.grade in [5, 6, 7, 8] else None,
        "language": _v(student, "language"),
        "guardian_name": _v(parent, "full_name") if parent else "",
        "guardian_relationship": _v(parent, "relationship") if parent else "",
        "guardian_phone": _v(parent, "phone_number") if parent else "",
        "guardian_phone2": _v(parent, "phone_number2") if parent else "",
        "teacher_name": _v(teacher, "full_name") if teacher else "",
        "teacher_workplace": _v(teacher, "workplace") if teacher else "",
        "teacher_phone": _v(teacher, "phone_number") if teacher else "",
        "source_type": getattr(source, "source_type", None) if source else "",
        "achievements_description": _v(student, "achievements_description"),
    }
    if getattr(student, "phone_owner", None):
        state_data["phone_owner"] = student.phone_owner
    if student.photo:
        state_data["photo"] = getattr(student.photo, "name", None) or str(student.photo) or ""

    # Stage 1: initial link (name -> phone -> phone owner)
    if not state_data["initial_full_name"]:
        return "waiting_for_initial_full_name", state_data
    if not (student.phone_number and str(student.phone_number).strip()):
        return "waiting_for_initial_phone", state_data
    phone_owner = getattr(student, "phone_owner", None)
    if not (phone_owner and str(phone_owner).strip()):
        return "waiting_for_phone_owner", state_data
    # Stage 1 done; Stage 2 not started (no first_name from olympiad form)
    if not state_data["first_name"]:
        return "waiting_for_olympiad_participation", state_data

    # Stage 2: olympiad registration steps (by required fields in DB)
    if not state_data["last_name"]:
        return "waiting_for_last_name", state_data
    if not student.date_of_birth:
        return "waiting_for_date_of_birth", state_data
    if not state_data["document_number"]:
        return "waiting_for_document_number", state_data
    if not state_data["region"]:
        return "waiting_for_region", state_data
    if not state_data["district"]:
        return "waiting_for_district", state_data
    if not state_data["school_name"]:
        return "waiting_for_school_name", state_data
    if student.grade not in (5, 6, 7, 8):
        return "waiting_for_grade", state_data
    if not (student.photo and str(student.photo).strip()):
        return "waiting_for_photo", state_data
    # Achievements are skippable; next required is guardian
    if not parent or not state_data["guardian_name"]:
        return "waiting_for_guardian_name", state_data
    if not state_data["guardian_relationship"]:
        return "waiting_for_guardian_relationship", state_data
    if not state_data["guardian_phone"]:
        return "waiting_for_guardian_phone", state_data
    # guardian_phone2 is optional (skip); next is teacher
    if not teacher or not state_data["teacher_name"]:
        return "waiting_for_teacher_name", state_data
    if not state_data["teacher_phone"]:
        return "waiting_for_teacher_phone", state_data
    if not source or not state_data["source_type"]:
        return "waiting_for_source", state_data
    # All data present but not confirmed
    return "waiting_for_confirmation", state_data


async def _get_state_data(telegram_id: int):
    state_obj = await BotStateService.get_state(telegram_id)
    return state_obj.state_data if state_obj else {}


@router.message(F.text == "⬅️ Ortga")
async def process_back_message(message: Message, state: FSMContext):
    """Handle back button (Reply)."""
    current_state = await state.get_state()
    telegram_id = message.from_user.id
    data = await _get_state_data(telegram_id)
    
    if current_state == RegistrationStates.waiting_for_initial_phone:
        await message.answer(GREETING_MESSAGE)
        await state.set_state(RegistrationStates.waiting_for_initial_full_name)
    
    # Update state in DB
    new_state = await state.get_state()
    await BotStateService.set_state(telegram_id, new_state)


@router.callback_query(F.data == "back")
async def process_back_callback(callback: CallbackQuery, state: FSMContext):
    """Handle back button (Inline)."""
    current_state = await state.get_state()
    telegram_id = callback.from_user.id
    data = await _get_state_data(telegram_id)
    
    if current_state == RegistrationStates.waiting_for_phone_owner:
        await _safe_delete_message(callback.message, "check_subs")
        await callback.message.answer(STEP_INITIAL_PHONE, reply_markup=get_phone_keyboard())
        await state.set_state(RegistrationStates.waiting_for_initial_phone)
        
    elif current_state == RegistrationStates.waiting_for_olympiad_participation:
        await callback.message.delete()
        await callback.message.answer(STEP_PHONE_OWNER, reply_markup=get_phone_owner_keyboard())
        await state.set_state(RegistrationStates.waiting_for_phone_owner)

    new_state = await state.get_state()
    await BotStateService.set_state(telegram_id, new_state)
    await callback.answer()


@router.callback_query(F.data == "check_subs")
async def check_subs(callback: CallbackQuery, state: FSMContext):
    """Check subscription callback. When in waiting_for_channels and subscribed, continue registration flow."""
    telegram_id = callback.from_user.id
    subscription_status = await SubscriptionService.check_subscription(callback.bot, telegram_id)

    if not subscription_status['subscribed']:
        channels = subscription_status['missing_channels']
        keyboard = build_channel_keyboard(channels)
        try:
            await callback.message.edit_text(CHECK_SUBS_FAIL, reply_markup=keyboard)
        except Exception:
            await callback.message.answer(CHECK_SUBS_FAIL, reply_markup=keyboard)
        await callback.answer(CHECK_SUBS_NOT_CONFIRMED)
        return

    current_state = await state.get_state()
    if current_state == RegistrationStates.waiting_for_channels:
        state_obj = await BotStateService.get_state(telegram_id)
        data = (state_obj.state_data or {}) if state_obj else {}
        after_channels = data.get("after_channels")
        await callback.message.delete()
        await callback.answer(CHECK_SUBS_CONFIRMED_ANSWER)

        if after_channels == "full_reg":
            await _award_referral_and_notify(telegram_id, callback.bot)
            await callback.message.answer(SUCCESS_MESSAGE)
            await callback.message.answer(MENU_PROMPT, reply_markup=get_main_menu_keyboard(telegram_id=callback.from_user.id))
            await state.clear()
            await BotStateService.clear_state(telegram_id)
        elif after_channels == "other_grade":
            await callback.message.answer(OTHER_GRADE_PROMO_MESSAGE, reply_markup=get_post_reg_promo_keyboard())
            await state.set_state(RegistrationStates.waiting_for_post_reg_promo)
            await BotStateService.set_state(telegram_id, "waiting_for_post_reg_promo")
        else:
            await callback.message.answer(CHECK_SUBS_SUCCESS)
        return

    await _safe_delete_message(callback.message, "phone_owner")
    await callback.message.answer(CHECK_SUBS_SUCCESS)
    await callback.answer(CHECK_SUBS_CONFIRMED_ANSWER)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command. Supports referral: /start REF_CODE. Channel join is asked at end of registration.
    If user is in the middle of registration, resume from that step."""
    telegram_id = message.from_user.id
    username = message.from_user.username
    ref_code = _parse_start_referral(message.text or "")
    logger.info("/start from user %s | raw text: %r | parsed ref_code: %r", telegram_id, message.text, ref_code)

    # Track referral (partner or student) as early as possible so it's captured
    # even for returning users who get resumed into their registration flow below.
    if ref_code and ref_code != str(telegram_id):
        student_obj, _ = await StudentService.get_or_create_student(telegram_id, username)
        if ref_code.startswith('ptr_'):
            logger.info("Partner ref_code detected: %s for user %s", ref_code, telegram_id)
            partner = await StudentService.get_partner_by_referral_code(ref_code)
            if partner:
                logger.info("Partner found: %s (id=%s) for user %s", partner.name, partner.id, telegram_id)
                await StudentService.set_partner(telegram_id, partner)
            else:
                logger.warning("No active partner found for code: %s", ref_code)
        else:
            logger.info("Student referral code detected: %r for user %s", ref_code, telegram_id)
            referrer = await StudentService.get_student_by_referral_code(ref_code)
            if referrer and referrer.first_name and referrer.last_name and referrer.document_number:
                logger.info("Referrer found: %s (id=%s)", referrer.first_name, referrer.telegram_id)
                await StudentService.set_referrer(telegram_id, referrer)
                await _award_referral_and_notify(telegram_id, message.bot)
            elif referrer:
                logger.warning("Referrer %s not fully registered, skipping", referrer.telegram_id)
            else:
                logger.warning("No student found for referral code: %r", ref_code)

    # If user has a saved registration state, resume from there (re-send current step).
    # Only resume if the Student still exists; otherwise they were deleted and we start fresh.
    state_obj = await BotStateService.get_state(telegram_id)
    student_exists = await StudentService.get_student(telegram_id) is not None
    if state_obj and state_obj.state in REGISTRATION_STATE_NAMES and student_exists:
        resume_state = state_obj.state
        # When resuming from editing_field, show "which field to edit" so user can pick again
        if resume_state == "editing_field":
            resume_state = "waiting_for_edit_field"
        reg_state = getattr(RegistrationStates, resume_state, None)
        if reg_state is not None:
            await state.set_state(reg_state)
            data = state_obj.state_data or {}
            text, reply_markup = await _get_continuation_for_state(
                telegram_id, resume_state, data, message.bot
            )
            if text is not None:
                if state_obj.state in WELCOME_VIDEO_STATES:
                    await _send_welcome_video_if_exists(message)
                if state_obj.state == "waiting_for_channels" and data.get("after_channels") == "full_reg" and text == SUCCESS_MESSAGE:
                    await _award_referral_and_notify(telegram_id, message.bot)
                    await message.answer(SUCCESS_MESSAGE)
                    await message.answer(MENU_PROMPT, reply_markup=reply_markup)
                    await state.clear()
                    await BotStateService.clear_state(telegram_id)
                elif state_obj.state == "waiting_for_channels" and data.get("after_channels") == "other_grade":
                    await message.answer(text, reply_markup=reply_markup)
                    await state.set_state(RegistrationStates.waiting_for_post_reg_promo)
                    await BotStateService.set_state(telegram_id, "waiting_for_post_reg_promo")
                else:
                    kwargs = {"reply_markup": reply_markup}
                    if text == REFERRAL_ONLY_PROMO_TEXT:
                        kwargs["link_preview_options"] = LinkPreviewOptions(is_disabled=True)
                    await message.answer(text, **kwargs)
                return
            # Fall through if continuation returned None

    # Stale state (e.g. user was deleted from DB): clear so we start fresh below
    if state_obj and state_obj.state in REGISTRATION_STATE_NAMES and not student_exists:
        await BotStateService.clear_state(telegram_id)
        await state.clear()

    # Get or create student (may already exist from the early referral block above)
    student, created = await StudentService.get_or_create_student(telegram_id, username)

    # When saved state is missing (e.g. after deployment), infer where the user stopped from DB and resume there
    if not (state_obj and state_obj.state in REGISTRATION_STATE_NAMES and student_exists):
        inferred_state, inferred_data = await _infer_registration_state_from_db(telegram_id)
        if inferred_state:
            reg_state = getattr(RegistrationStates, inferred_state, None)
            if reg_state is not None:
                await state.set_state(reg_state)
                await BotStateService.set_state(telegram_id, inferred_state, inferred_data)
                text, reply_markup = await _get_continuation_for_state(
                    telegram_id, inferred_state, inferred_data, message.bot
                )
                if text is None:
                    text = GREETING_MESSAGE
                    reply_markup = None
                if inferred_state in WELCOME_VIDEO_STATES:
                    await _send_welcome_video_if_exists(message)
                kwargs = {"reply_markup": reply_markup} if reply_markup else {}
                if text == REFERRAL_ONLY_PROMO_TEXT:
                    kwargs["link_preview_options"] = LinkPreviewOptions(is_disabled=True)
                await message.answer(text, **kwargs)
                return

    # No registration state to resume: show video then decide by student data
    await _send_welcome_video_if_exists(message)

    # Check if user has phone number - if not, restart Stage 1 registration
    if not student.phone_number or not student.phone_number.strip():
        # No phone number - start from beginning (Stage 1: Name -> Phone -> Owner)
        await message.answer(GREETING_MESSAGE)
        await state.set_state(RegistrationStates.waiting_for_initial_full_name)
        await BotStateService.set_state(telegram_id, "waiting_for_initial_full_name")
        return

    if student.registered_from_web or (student.first_name and student.last_name and student.date_of_birth and student.document_number):
        # Student already registered (via Web App or full 17-step flow)
        display_name = student.first_name or student.initial_full_name or ""
        await message.answer(
            ALREADY_REGISTERED.format(first_name=display_name),
            reply_markup=get_main_menu_keyboard(telegram_id=telegram_id)
        )
        await state.clear()
        
    elif student.initial_full_name:
        # Stage 1 completed, prompt for Stage 2 (Promo)
        await message.answer(PROMO_TEXT, reply_markup=get_olympiad_participation_keyboard())
        await state.set_state(RegistrationStates.waiting_for_olympiad_participation)
        await BotStateService.set_state(telegram_id, "waiting_for_olympiad_participation")
    
    else:
        # Start Stage 1 registration (Name -> Phone -> Owner)
        await message.answer(GREETING_MESSAGE)
        await state.set_state(RegistrationStates.waiting_for_initial_full_name)
        await BotStateService.set_state(telegram_id, "waiting_for_initial_full_name")


    # /reg command removed: /start handles everything


@router.message(F.web_app_data)
async def handle_reg_webapp_data(message: Message, state: FSMContext):
    """Process form submission from the registration Web App (full form after 3 chat steps). Saves data for the current user (telegram_id)."""
    if not message.from_user or not message.web_app_data:
        return
    try:
        data = json.loads(message.web_app_data.data)
    except (ValueError, TypeError) as e:
        logger.warning("Invalid web_app_data from reg app: %s", e)
        await message.answer("Xatolik: noto'g'ri ma'lumot. Qaytadan urinib ko'ring.")
        return

    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    phone_number = _normalize_phone((data.get("phone_number") or ""))
    region = (data.get("region") or "").strip() or None
    district = (data.get("district") or "").strip() or None
    grade_raw = data.get("grade")
    grade = None
    if grade_raw is not None:
        if str(grade_raw) == 'other':
            grade = 0
        elif str(grade_raw).isdigit():
            g = int(grade_raw)
            if g in (0, 5, 6, 7, 8):
                grade = g
    school_name = (data.get("school_name") or "").strip() or None
    document_number = (data.get("document_number") or "").strip() or None
    guardian_name = (data.get("guardian_name") or "").strip() or None
    guardian_phone = _normalize_phone((data.get("guardian_phone") or "")) or None
    if guardian_phone and len(guardian_phone) > 20:
        guardian_phone = None
    teacher_name = (data.get("teacher_name") or "").strip() or None
    teacher_phone = _normalize_phone((data.get("teacher_phone") or "")) or None
    if teacher_phone and len(teacher_phone) > 20:
        teacher_phone = None

    telegram_id = message.from_user.id
    payload_user_id = data.get("user_id")
    if payload_user_id is not None:
        try:
            payload_uid = int(payload_user_id)
            if payload_uid != telegram_id:
                await message.answer("Xatolik: foydalanuvchi mos emas. Ilova orqali qayta oching.")
                return
        except (TypeError, ValueError):
            pass

    username = message.from_user.username if message.from_user.username else None

    student = await StudentService.get_student(telegram_id)
    if not student:
        await StudentService.get_or_create_student(telegram_id, username)
        student = await StudentService.get_student(telegram_id)
    if not student:
        await message.answer("Xatolik: ro'yxatdan o'tishda muammo. Qaytadan urinib ko'ring.")
        return

    if document_number:
        existing = await StudentService.get_student_by_document_number(document_number.upper())
        if existing and existing.telegram_id != telegram_id:
            await message.answer(
                "❌ Bu Metrika raqami boshqa foydalanuvchi ro'yxatida mavjud. "
                "Iltimos, to'g'ri raqam kiriting yoki bo'sh qoldiring."
            )
            return

    try:
        await StudentService.update_student_webapp(
            telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            region=region,
            district=district,
            grade=grade,
            school_name=school_name,
            document_number=document_number,
        )
        await StudentService.update_student(telegram_id, registered_from_web=True)
        student = await StudentService.get_student(telegram_id)
        if not student:
            await message.answer("Xatolik: saqlashda muammo. Qaytadan urinib ko'ring.")
            return
        if guardian_name:
            await StudentService.create_parent(student, guardian_name, phone_number=guardian_phone)
            await StudentService.update_parent(student, full_name=guardian_name, phone_number=guardian_phone or None)
        if teacher_name:
            await StudentService.create_teacher(student, teacher_name, phone_number=teacher_phone)
            await StudentService.update_teacher(student, full_name=teacher_name, phone_number=teacher_phone or None)
    except IntegrityError as e:
        logger.warning("IntegrityError saving reg webapp data for telegram_id=%s: %s", telegram_id, e)
        if "document_number" in str(e).lower() or "unique" in str(e).lower():
            await message.answer(
                "❌ Bu Metrika raqami boshqa foydalanuvchi ro'yxatida mavjud. "
                "Iltimos, to'g'ri raqam kiriting yoki bo'sh qoldiring."
            )
            return
        await message.answer("Xatolik: ma'lumotlarni saqlashda muammo yuz berdi. Qaytadan urinib ko'ring.")
        return

    await state.clear()
    await BotStateService.clear_state(telegram_id)

    is_other_grade = (grade == 0)
    success_text = OTHER_GRADE_SUCCESS_MESSAGE if is_other_grade else SUCCESS_MESSAGE
    await message.answer(success_text, reply_markup=get_main_menu_keyboard(other_grade=is_other_grade, telegram_id=telegram_id))

    # Schedule 30-second delayed promo message (different for "other" grade)
    if is_other_grade:
        asyncio.create_task(_send_delayed_other_grade_promo(message.bot, telegram_id))
    else:
        asyncio.create_task(_send_delayed_contest_promo(message.bot, telegram_id))


@router.callback_query(F.data == "reg_main_menu")
async def callback_reg_main_menu(callback: CallbackQuery, state: FSMContext):
    """After Web App reg: show main menu."""
    await callback.answer()
    await state.clear()
    await callback.message.answer(MENU_PROMPT, reply_markup=get_main_menu_keyboard(telegram_id=callback.from_user.id))


@router.callback_query(F.data == "reg_participate_contest")
async def callback_reg_participate_contest(callback: CallbackQuery, state: FSMContext):
    """After Web App reg: participate in 100$ contest."""
    await callback.answer()
    await callback.message.answer(
        "🏆 <b>Konkursda qatnashish</b>\n\n"
        "100$ gacha mukofot olish uchun konkursda qatnashing! "
        "Batafsil ma'lumot uchun kanalimizga obuna bo'ling: @rs_olimpiada / @RahimovSchool"
    )


@router.callback_query(F.data == "reg_participate_test")
async def callback_reg_participate_test(callback: CallbackQuery, state: FSMContext):
    """After Web App reg: participate in test (navigate to test flow)."""
    from bot.handlers.test import send_test_to_user
    await callback.answer()
    telegram_id = callback.from_user.id
    student = await StudentService.get_student(telegram_id)
    if not student or not student.grade:
        await callback.message.answer("❌ Avval ro'yxatdan o'ting!")
        return
    pending = await TestService.get_pending_attempt_for_student(student)
    if pending:
        test = pending.test
    else:
        tests = await TestService.get_active_tests_for_grade_and_language(student.grade, student.language)
        if not tests:
            await callback.message.answer("❌ Sizning sinfingiz uchun test hozircha mavjud emas.")
            return
        test = tests[0]
    if not test:
        await callback.message.answer("❌ Sizning sinfingiz uchun test hozircha mavjud emas.")
        return
    await send_test_to_user(callback.message, student, test)


# ==================== STAGE 1: INITIAL REGISTRATION ====================

@router.message(StateFilter(RegistrationStates.waiting_for_initial_full_name))
async def process_initial_full_name(message: Message, state: FSMContext):
    """Process initial full name."""
    full_name = message.text.strip() if message.text else ""

    telegram_id = message.from_user.id

    # Save name to Student model immediately
    await StudentService.update_student(telegram_id, initial_full_name=full_name)

    # Carry forward accumulated state data
    state_data_obj = await BotStateService.get_state(telegram_id)
    data = (state_data_obj.state_data if state_data_obj else {}) or {}
    data['initial_full_name'] = full_name

    await state.set_state(RegistrationStates.waiting_for_initial_phone)
    await BotStateService.set_state(telegram_id, "waiting_for_initial_phone", data)
    
    await message.answer(STEP_INITIAL_PHONE, reply_markup=get_phone_keyboard())


@router.message(StateFilter(RegistrationStates.waiting_for_initial_phone))
async def process_initial_phone(message: Message, state: FSMContext):
    """Process initial phone number."""
    phone = None
    if message.contact:
        phone = message.contact.phone_number
    elif message.text:
        phone = message.text.strip()
    
    phone = _normalize_phone(phone or "")
    if not phone or len(phone) < 9 or len(phone) > 20:
        await message.answer(ERROR_INVALID_PHONE_UZB)
        return

    telegram_id = message.from_user.id

    # Save phone to Student model immediately so the webapp form can read it
    await StudentService.update_student(telegram_id, phone_number=phone)

    # Carry forward accumulated state data (initial_full_name from step 1)
    state_data_obj = await BotStateService.get_state(telegram_id)
    data = (state_data_obj.state_data if state_data_obj else {}) or {}
    data['initial_phone'] = phone

    await state.set_state(RegistrationStates.waiting_for_phone_owner)
    await BotStateService.set_state(telegram_id, "waiting_for_phone_owner", data)

    await message.answer(STEP_PHONE_OWNER, reply_markup=get_phone_owner_keyboard())


@router.callback_query(StateFilter(RegistrationStates.waiting_for_phone_owner))
async def process_phone_owner(callback: CallbackQuery, state: FSMContext):
    """Process phone owner selection."""
    if not callback.data.startswith('phone_owner_'):
        await callback.answer(ERROR_USE_BUTTONS)
        return

    # Delete message
    await _safe_delete_message(callback.message, "check_subs")

    owner_type = callback.data.replace('phone_owner_', '') # self/spouse/other
    
    # Map to model choices: 'ozimniki', 'turmush_ortogim', 'boshqa'
    # Callback: self -> ozimniki, spouse -> turmush_ortogim, other -> boshqa
    model_choice = 'boshqa'
    if owner_type == 'self':
        model_choice = 'ozimniki'
    elif owner_type == 'spouse':
        model_choice = 'turmush_ortogim'
    
    telegram_id = callback.from_user.id
    state_data_obj = await BotStateService.get_state(telegram_id)
    state_data = state_data_obj.state_data if state_data_obj else {}
    
    initial_full_name = state_data.get('initial_full_name', '')
    initial_phone = state_data.get('initial_phone', '')
    
    # SAVE Stage 1 Data to Student Model
    await StudentService.update_student(
        telegram_id,
        initial_full_name=initial_full_name,
        phone_number=initial_phone, 
        phone_owner=model_choice
    )
    
    await callback.answer()

    # Send reg greeting and Web App button (form: first_name, last_name, region, etc.) with user_id + phone in URL
    web_app_url = _reg_webapp_url_with_user(telegram_id, phone=initial_phone)
    if not web_app_url:
        await callback.message.answer(
            "⚠️ Web App sozlanmagan. ADMIN: REG_WEBAPP_URL ni sozlang.",
        )
        await state.set_state(RegistrationStates.waiting_for_olympiad_participation)
        await BotStateService.set_state(telegram_id, "waiting_for_olympiad_participation")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=REG_BUTTON_LABEL, web_app=WebAppInfo(url=web_app_url))]
    ])
    await callback.message.answer(REG_GREETING_MESSAGE, reply_markup=keyboard)
    await state.set_state(RegistrationStates.waiting_for_webapp_reg)
    await BotStateService.set_state(telegram_id, "waiting_for_webapp_reg")


@router.callback_query(StateFilter(RegistrationStates.waiting_for_olympiad_participation))
async def process_olympiad_choice(callback: CallbackQuery, state: FSMContext):
    """Process olympiad participation choice."""
    telegram_id = callback.from_user.id
    await callback.message.delete()
    
    if callback.data == 'olympiad_yes':
         await callback.message.answer(OLYMPIAD_INTRO)
         
         # Start Stage 2 (Step 1)
         await state.set_state(RegistrationStates.waiting_for_first_name)
         await BotStateService.set_state(telegram_id, "waiting_for_first_name")
    
    elif callback.data == 'olympiad_no':
         # Auto-register with basic info for referral
         first_name = callback.from_user.first_name
         last_name = callback.from_user.last_name
         await StudentService.update_student(telegram_id, first_name=first_name, last_name=last_name)
         
         # Show Referral Promo Text + "Ha" button to get link
         await callback.message.answer(
             REFERRAL_ONLY_PROMO_TEXT,
             reply_markup=get_post_reg_promo_keyboard(),
             link_preview_options=LinkPreviewOptions(is_disabled=True),
         )
         
         # Wait for "accept_promo" (Ha)
         await state.set_state(RegistrationStates.waiting_for_post_reg_promo)
         await BotStateService.set_state(telegram_id, "waiting_for_post_reg_promo")
    
    await callback.answer()


@router.message(F.text == "👥 Do'stlarni taklif qilish")
async def handle_referral_menu(message: Message, state: FSMContext):
    """Show REFERRAL_ONLY_PROMO_TEXT with Ha button; on Yes → promo message with image."""
    telegram_id = message.from_user.id
    student = await StudentService.get_student(telegram_id)
    # Relaxed check: allow if just first_name exists (referral agent)
    if not student or not student.first_name:
        await message.answer(ERROR_NOT_REGISTERED)
        return

    await message.answer(
        REFERRAL_ONLY_PROMO_TEXT,
        reply_markup=get_referral_menu_confirm_keyboard(),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


@router.callback_query(F.data == "referral_menu_accept")
async def referral_menu_accept(callback: CallbackQuery, state: FSMContext):
    """Send PROMO_MESSAGE with image when user clicks Ha from referral menu."""
    telegram_id = callback.from_user.id
    student = await StudentService.get_student(telegram_id)
    if not student or not student.first_name:
        await _safe_callback_answer(callback, ERROR_NOT_REGISTERED)
        return

    bot_me = await callback.bot.get_me()
    bot_username = bot_me.username if bot_me else ""
    ref_code = student.referral_code or str(telegram_id)
    referral_link = f"https://t.me/{bot_username}?start={ref_code}" if bot_username else ""
    promo_text = PROMO_MESSAGE.format(referral_link=referral_link)

    photo_path = os.path.join(settings.MEDIA_ROOT, "rmo_logo.jpg")
    if os.path.exists(photo_path):
        await callback.message.answer_photo(
            FSInputFile(photo_path),
            caption=promo_text,
            parse_mode=ParseMode.HTML,
        )
    else:
        await callback.message.answer(promo_text)

    await _safe_delete_message(callback.message, "referral_menu_accept")
    await _safe_callback_answer(callback)


@router.callback_query(F.data == "referral_menu_back")
async def referral_menu_back(callback: CallbackQuery, state: FSMContext):
    """Show REFERRAL_DESC (link + points) when user clicks Ortga from referral menu."""
    telegram_id = callback.from_user.id
    student = await StudentService.get_student(telegram_id)
    if not student or not student.first_name:
        await _safe_callback_answer(callback, ERROR_NOT_REGISTERED)
        return

    ref_code = student.referral_code or str(telegram_id)
    bot_me = await callback.bot.get_me()
    bot_username = bot_me.username if bot_me else ""
    referral_link = f"https://t.me/{bot_username}?start={ref_code}" if bot_username else ""
    text = REFERRAL_DESC.format(referral_link=referral_link)

    try:
        await callback.message.edit_text(text)
    except TelegramBadRequest:
        await callback.message.answer(text)
    await _safe_callback_answer(callback)


@router.message(F.text == "🔥 Konkursdagi ballarim")
async def handle_my_contest_scores(message: Message, state: FSMContext):
    """Show user's contest scores/points."""
    telegram_id = message.from_user.id
    student = await StudentService.get_student(telegram_id)
    if not student or not student.first_name:
        await message.answer(ERROR_NOT_REGISTERED)
        return

    rank, points = await StudentService.get_user_referral_rank_and_points(telegram_id)
    text = (
        "🔥 <b>Konkursdagi ballaringiz</b>\n\n"
        f"📊 Referral ballaringiz: <b>{points}</b> ball\n"
        f"🫂 Nechta odam taklif qildingiz? — {points//5} ta\n"
    )
    if rank is not None:
        text += f"🏅 Reytingdagi o'rningiz: <b>{rank}</b>\n"
    text += "\nKo'proq ball to'plash uchun do'stlaringizni taklif qiling!"
    await message.answer(text)


@router.message(F.text == "🏆 Reyting")
async def handle_leaderboard(message: Message, state: FSMContext):
    """Show referral leaderboard with fresh data."""
    telegram_id = message.from_user.id
    student = await StudentService.get_student(telegram_id)
    if not student or not student.first_name:
        await message.answer(ERROR_NOT_REGISTERED)
        return

    # Fetch leaderboard and user rank+points from fresh DB queries
    leaderboard = await StudentService.get_referral_leaderboard(limit=10)
    rank, user_points = await StudentService.get_user_referral_rank_and_points(telegram_id)

    text = LEADERBOARD_TITLE

    if leaderboard:
        for i, row in enumerate(leaderboard, 1):
            name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip() or "—"
            pts = row.get('referral_points') or 0
            if row.get('telegram_id') == telegram_id:
                name = f"<b>{name}</b>"
            text += f"{i}. {name} — {pts//5} ta\n"
    else:
        text += LEADERBOARD_EMPTY

    if rank is not None and rank > 10:
        text += "\n____\n\n"
        text += LEADERBOARD_USER_RANK.format(rank=rank, user_points=user_points//5)

    await message.answer(text)


@router.message(F.text == "👨‍🏫 Ustozlar reytingi")
async def handle_teachers_leaderboard(message: Message, state: FSMContext):
    """Show teachers leaderboard by number of students."""
    telegram_id = message.from_user.id
    student = await StudentService.get_student(telegram_id)
    if not student or not student.first_name:
        await message.answer(ERROR_NOT_REGISTERED)
        return

    # Fetch teachers leaderboard
    leaderboard = await StudentService.get_teachers_leaderboard(limit=10)

    from bot.constants import TEACHER_LEADERBOARD_TITLE, TEACHER_LEADERBOARD_EMPTY, TEACHER_LEADERBOARD_ROW
    text = TEACHER_LEADERBOARD_TITLE

    if leaderboard:
        # leaderboard is a list of dicts: {'phone_number': ..., 'student_count': ..., 'full_name': ...}
        for i, row in enumerate(leaderboard, 1):
            name = row.get('full_name', '') or "Noma'lum"
            cnt = row.get('student_count') or 0
            text += TEACHER_LEADERBOARD_ROW.format(rank=i, teacher_name=name, student_count=cnt)
    else:
        text += TEACHER_LEADERBOARD_EMPTY

    await message.answer(text)




@router.callback_query(StateFilter(RegistrationStates.waiting_for_post_reg_promo), F.data == "accept_promo")
async def accept_referral_promo(callback: CallbackQuery, state: FSMContext):
    """Handle referral promo acceptance (olympiad_no, grade_other flows)."""
    telegram_id = callback.from_user.id

    await _award_referral_and_notify(telegram_id, callback.bot)

    await state.clear()
    await BotStateService.clear_state(telegram_id)

    student = await StudentService.get_student(telegram_id)

    # Generate link
    bot_me = await callback.bot.get_me()
    bot_username = bot_me.username if bot_me else ""
    ref_code = (student.referral_code or str(telegram_id)) if student else str(telegram_id)
    referral_link = f"https://t.me/{bot_username}?start={ref_code}" if bot_username else ""
    
    promo_text = PROMO_MESSAGE.format(referral_link=referral_link)
    photo_path = os.path.join(settings.MEDIA_ROOT, 'rmo_logo.jpg')
    
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(photo, caption=promo_text, parse_mode=ParseMode.HTML)
        await callback.message.delete() # Delete the previous text message to avoid clutter
    else:
        await callback.message.edit_text(promo_text)
    
    await callback.message.answer(MENU_PROMPT, reply_markup=get_main_menu_keyboard(telegram_id=callback.from_user.id))
    await callback.answer()


async def _send_delayed_contest_promo(bot_instance, telegram_id: int):
    """Wait 30 seconds then send the contest promo teaser with inline button."""
    await asyncio.sleep(30)
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏆 Konkursda qatnashish", callback_data="contest_participate_promo")]
        ])
        await bot_instance.send_message(
            chat_id=telegram_id,
            text=PROMO_AFTER_REG_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.error("Failed to send delayed contest promo to %s: %s", telegram_id, e)


async def _send_delayed_other_grade_promo(bot_instance, telegram_id: int):
    """Wait 30 seconds then send the referral contest promo directly (for 'other' grade users)."""
    await asyncio.sleep(30)
    try:
        student = await StudentService.get_student(telegram_id)
        if not student:
            return
        bot_me = await bot_instance.get_me()
        bot_username = bot_me.username if bot_me else ""
        ref_code = student.referral_code or str(telegram_id)
        referral_link = f"https://t.me/{bot_username}?start={ref_code}" if bot_username else ""
        promo_text = OTHER_GRADE_PROMO_MESSAGE.format(referral_link=referral_link)

        photo_path = os.path.join(settings.MEDIA_ROOT, "rmo_logo.jpg")
        if os.path.exists(photo_path):
            sent_msg = await bot_instance.send_photo(
                chat_id=telegram_id,
                photo=FSInputFile(photo_path),
                caption=promo_text,
                parse_mode=ParseMode.HTML,
            )
        else:
            sent_msg = await bot_instance.send_message(
                chat_id=telegram_id,
                text=promo_text,
                parse_mode=ParseMode.HTML,
            )

        # Reply with referral note
        await bot_instance.send_message(
            chat_id=telegram_id,
            text=CONTEST_PROMO_REPLY,
            parse_mode=ParseMode.HTML,
            reply_to_message_id=sent_msg.message_id,
        )
    except Exception as e:
        logger.error("Failed to send other-grade promo to %s: %s", telegram_id, e)


async def _send_contest_promo_with_referral(message_or_bot, telegram_id: int, chat_id: int = None):
    """Send the contest promo photo with referral link, then reply with referral info."""
    student = await StudentService.get_student(telegram_id)
    if not student:
        return

    bot_instance = message_or_bot if hasattr(message_or_bot, 'get_me') else message_or_bot.bot
    bot_me = await bot_instance.get_me()
    bot_username = bot_me.username if bot_me else ""
    ref_code = student.referral_code or str(telegram_id)
    referral_link = f"https://t.me/{bot_username}?start={ref_code}" if bot_username else ""
    promo_text = CONTEST_PROMO_MESSAGE.format(referral_link=referral_link)

    target_chat = chat_id or telegram_id
    photo_path = os.path.join(settings.MEDIA_ROOT, "poster.jpg")

    if os.path.exists(photo_path):
        sent_msg = await bot_instance.send_photo(
            chat_id=target_chat,
            photo=FSInputFile(photo_path),
            caption=promo_text,
            parse_mode=ParseMode.HTML,
        )
    else:
        sent_msg = await bot_instance.send_message(
            chat_id=target_chat,
            text=promo_text,
            parse_mode=ParseMode.HTML,
        )

    # Reply to that message with referral note
    await bot_instance.send_message(
        chat_id=target_chat,
        text=CONTEST_PROMO_REPLY,
        parse_mode=ParseMode.HTML,
        reply_to_message_id=sent_msg.message_id,
    )


@router.callback_query(F.data == "contest_participate_promo")
async def handle_contest_participate_promo(callback: CallbackQuery, state: FSMContext):
    """Handle contest participate inline button (from 30-sec delayed message or other)."""
    telegram_id = callback.from_user.id
    await callback.answer()
    await _send_contest_promo_with_referral(callback.bot, telegram_id, chat_id=callback.message.chat.id)


@router.message(F.text == "🏆 Konkursda qatnashish")
async def handle_contest_participate_menu(message: Message, state: FSMContext):
    """Handle contest participate from main menu reply keyboard."""
    telegram_id = message.from_user.id
    student = await StudentService.get_student(telegram_id)
    if not student or not student.first_name:
        await message.answer(ERROR_NOT_REGISTERED)
        return
    await _send_contest_promo_with_referral(message.bot, telegram_id, chat_id=message.chat.id)


@router.message(F.text == "📝 1-bosqich sinov testini yechish: 1-mart")
async def handle_test_from_menu(message: Message, state: FSMContext):
    """Handle test participation from main menu reply keyboard."""
    # If today is earlier than 22 Feb of the current year, show informational message
    today = datetime.now().date()
    mar1 = datetime(today.year, 3, 1).date()
    if today < mar1:
        await message.answer(
            "1-bosqich online sinov testi shu botda 1-mart kuni soat 14:00 da bo'lib o'tadi. Unga namunaviy testlarni yechib turishingiz mumkin:\n\nhttps://t.me/rs_olimpiada/24"
        )
        return

    from bot.handlers.test import send_test_to_user
    telegram_id = message.from_user.id
    student = await StudentService.get_student(telegram_id)
    if not student or not student.grade:
        await message.answer(ERROR_NOT_REGISTERED)
        return

    # Check for existing test attempts
    pending = await TestService.get_pending_attempt_for_student(student)
    if pending:
        # Check if already submitted
        if pending.status == 'SUBMITTED_FINAL':
            await message.answer(
                "✅ Siz allaqachon bu testni topshirgansiz.\n\n"
                "🏆 Kanalimizda umumiy natijalarni tez kunda e'lon qilamiz, kuzatishda davom eting:\n\n@rs_olimpiada"
            )
            return
        # Check if in progress
        if pending.status == 'IN_PROGRESS':
            await message.answer(
                "⚠️ Sizda allaqachon davom etayotgan test bor!\n\n"
                "Testni davom ettirish uchun /start buyrug'ini yuboring."
            )
            return
        # Attempt is pending, show it
        test = pending.test
    else:
        # Check if student has any active or submitted test for their grade
        existing_attempt = await TestService.check_student_has_active_or_submitted_test(student, student.grade)
        if existing_attempt:
            if existing_attempt.status == 'SUBMITTED_FINAL':
                await message.answer(
                    "✅ Siz allaqachon bu testni topshirgansiz.\n\n"
                    "🏆 Kanalimizda umumiy natijalarni tez kunda e'lon qilamiz, kuzatishda davom eting:\n\n@rs_olimpiada"
                )
                return
            if existing_attempt.status in ['IN_PROGRESS', 'FINISHED_REVIEW']:
                await message.answer(
                    "⚠️ Sizda allaqachon davom etayotgan test bor!\n\n"
                    "Testni davom ettirish uchun /start buyrug'ini yuboring."
                )
                return

        # Get available tests
        tests = await TestService.get_active_tests_for_grade_and_language(student.grade, student.language)
        if not tests:
            await message.answer("1-bosqich online testi shu botda 22-fevral kuni soat 14:00 da bo'lib o'tadi. Unga namunaviy testlarni yechib turishingiz mumkin:\n\nhttps://t.me/rs_olimpiada/24")
            return
        test = tests[0]

    await send_test_to_user(message, student, test)


@router.message(F.text == "👤 Mening ma'lumotlarim")
async def handle_my_info(message: Message, state: FSMContext):
    """Handle 'My Info' from main menu."""
    telegram_id = message.from_user.id
    student = await StudentService.get_student(telegram_id)
    if not student or not student.first_name:
        await message.answer(ERROR_NOT_REGISTERED)
        return
    
    web_app_url = _reg_webapp_url_with_user(message.from_user.id)
    info_text = "Rahimov Matematika Olimpiadasi ishtirokchisisiz\n\nQuyidagi tugma orqali shaxsiy ma'lumotlaringizni tekshiringiz mumkin:"
    button = InlineKeyboardButton(text="👤 Mening ma'lumotlarim", web_app=WebAppInfo(url=web_app_url))
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])
    await message.answer(info_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


