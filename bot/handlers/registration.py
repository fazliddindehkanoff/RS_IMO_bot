import logging
import os
import asyncio
from datetime import datetime
from pathlib import Path

from aiogram import Router, F
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, LinkPreviewOptions, Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async
from django.conf import settings

from bot.constants import (
    GREETING_MESSAGE, STEP_INITIAL_PHONE, STEP_PHONE_OWNER, SUCCESS_INITIAL_REG,
    PROMO_TEXT, OLYMPIAD_INTRO, OLYMPIAD_DECLINED,     REFERRAL_ONLY_PROMO_TEXT,
    STEP_1_ASK_NAME, STEP_2_ASK_SURNAME, STEP_3_ASK_DOB, STEP_4_ASK_METRIKA,
    STEP_5_ASK_REGION, STEP_6_ASK_DISTRICT, STEP_7_ASK_SCHOOL, STEP_8_ASK_GRADE,
    STEP_9_ASK_PHOTO, STEP_10_ASK_ACHIEVEMENTS, STEP_11_ASK_GUARDIAN_NAME,
    STEP_12_ASK_RELATIONSHIP, STEP_13_ASK_GUARDIAN_PHONE, STEP_14_ASK_TEACHER_NAME,
    STEP_15_ASK_TEACHER_PHONE, STEP_16_ASK_SOURCE, STEP_17_CONFIRMATION_HEADER,
    SUCCESS_MESSAGE, PROMO_MESSAGE, ERROR_NAME_LENGTH, ERROR_SURNAME_LENGTH,
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
    get_olympiad_participation_keyboard, get_back_reply_keyboard, get_back_keyboard
)
from bot.services import BotStateService, StudentService, SubscriptionService
from bot.states import RegistrationStates
from admin_panel.models import RegistrationSource, Student, Parent, Teacher
from admin_panel.utils import send_referral_notification

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


def _build_channel_keyboard(missing_channels):
    """Build inline keyboard for mandatory channels + check button."""
    keyboard = []
    for ch in missing_channels:
        link = ch.channel_username
        if not link and ch.channel_id.startswith('@'):
            link = f"https://t.me/{ch.channel_id[1:]}"
        if not link:
            link = "https://t.me/"
        keyboard.append([InlineKeyboardButton(text=f"📢 {ch.title}", url=link)])
    keyboard.append([InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_subs")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# All registration state names stored in BotStateService (used for /start resume)
REGISTRATION_STATE_NAMES = {
    "waiting_for_initial_full_name", "waiting_for_initial_phone", "waiting_for_phone_owner",
    "waiting_for_olympiad_participation",
    "waiting_for_first_name", "waiting_for_last_name", "waiting_for_date_of_birth",
    "waiting_for_document_number", "waiting_for_region", "waiting_for_district",
    "waiting_for_school_name", "waiting_for_grade", "waiting_for_language",
    "waiting_for_photo", "waiting_for_achievements_description", "waiting_for_achievements_file",
    "waiting_for_guardian_name", "waiting_for_guardian_relationship", "waiting_for_guardian_age",
    "waiting_for_guardian_profession", "waiting_for_guardian_phone", "waiting_for_guardian_phone2",
    "waiting_for_teacher_name", "waiting_for_teacher_workplace", "waiting_for_teacher_phone",
    "waiting_for_source", "waiting_for_confirmation", "waiting_for_channels",
    "waiting_for_post_reg_promo", "waiting_for_edit_field", "editing_field",
}


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
    if state_name == "waiting_for_olympiad_participation":
        return (PROMO_TEXT, get_olympiad_participation_keyboard())
    if state_name == "waiting_for_first_name":
        return (STEP_1_ASK_NAME, get_back_reply_keyboard())
    if state_name == "waiting_for_last_name":
        first_name = d.get("first_name", "")
        return (STEP_2_ASK_SURNAME.format(first_name=first_name), get_back_reply_keyboard())
    if state_name == "waiting_for_date_of_birth":
        return (STEP_3_ASK_DOB, get_back_reply_keyboard())
    if state_name == "waiting_for_document_number":
        date_str = d.get("date_of_birth", "")
        return (STEP_4_ASK_METRIKA.format(date_str=date_str), get_back_reply_keyboard())
    if state_name == "waiting_for_region":
        doc = d.get("document_number", "")
        return (STEP_5_ASK_REGION.format(document_number=doc), get_region_keyboard())
    if state_name == "waiting_for_district":
        region = d.get("region", "")
        region_label = dict(Student.REGION_CHOICES).get(region, "")
        return (STEP_6_ASK_DISTRICT.format(region_label=region_label), get_back_reply_keyboard())
    if state_name == "waiting_for_school_name":
        return (STEP_7_ASK_SCHOOL.format(district=d.get("district", "")), get_back_reply_keyboard())
    if state_name == "waiting_for_grade":
        return (STEP_8_ASK_GRADE.format(school_name=d.get("school_name", "")), get_grade_keyboard())
    if state_name == "waiting_for_photo":
        return (STEP_9_ASK_PHOTO, get_back_keyboard())
    if state_name in ("waiting_for_achievements_description", "waiting_for_achievements_file"):
        return (STEP_10_ASK_ACHIEVEMENTS, get_skip_keyboard())
    if state_name == "waiting_for_guardian_name":
        return (STEP_11_ASK_GUARDIAN_NAME, get_back_reply_keyboard())
    if state_name == "waiting_for_guardian_relationship":
        return (STEP_12_ASK_RELATIONSHIP, get_relationship_keyboard())
    if state_name in ("waiting_for_guardian_phone", "waiting_for_guardian_age", "waiting_for_guardian_profession"):
        relation_text = RELATION_SUFFIX_MAP.get(d.get("guardian_relationship", ""), "Vasiyingiz")
        return (STEP_13_ASK_GUARDIAN_PHONE.format(relation_text=relation_text), get_back_reply_keyboard())
    if state_name == "waiting_for_guardian_phone2":
        relation_text = RELATION_SUFFIX_MAP.get(d.get("guardian_relationship", ""), "Vasiyingiz")
        return (STEP_13_ASK_GUARDIAN_PHONE.format(relation_text=relation_text), get_back_reply_keyboard())
    if state_name in ("waiting_for_teacher_name", "waiting_for_teacher_workplace"):
        return (STEP_14_ASK_TEACHER_NAME, get_back_reply_keyboard())
    if state_name == "waiting_for_teacher_phone":
        return (STEP_15_ASK_TEACHER_PHONE, get_back_reply_keyboard())
    if state_name == "waiting_for_source":
        return (STEP_16_ASK_SOURCE, get_source_type_keyboard())
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
                return (SUCCESS_MESSAGE, get_main_menu_keyboard())
            if after == "other_grade":
                return (OTHER_GRADE_PROMO_MESSAGE, get_post_reg_promo_keyboard())
            return (CHECK_SUBS_SUCCESS, None)
        kb = _build_channel_keyboard(subscription_status["missing_channels"])
        return (CHECK_SUBS_START, kb)
    if state_name == "waiting_for_post_reg_promo":
        if d.get("school_name"):
            return (OTHER_GRADE_PROMO_MESSAGE, get_post_reg_promo_keyboard())
        return (REFERRAL_ONLY_PROMO_TEXT, get_post_reg_promo_keyboard())
    if state_name in ("waiting_for_edit_field", "editing_field"):
        return (EDIT_TITLE, get_edit_fields_keyboard())
    if state_name == "waiting_for_language":
        return (STEP_9_ASK_PHOTO, get_back_keyboard())
    return (None, None)


def _parse_start_referral(message_text: str) -> str | None:
    """Parse /start payload: /start REF_CODE -> return REF_CODE or None."""
    if not message_text or not message_text.strip().startswith("/start"):
        return None
    parts = message_text.strip().split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else None


async def _infer_registration_state_from_db(telegram_id: int):
    """Infer where the user stopped in registration from Student/Parent/Teacher/Source DB.
    Returns (state_name, state_data) or (None, {}) if fully registered or nothing to resume."""
    student = await StudentService.get_student(telegram_id)
    if not student:
        return None, {}

    # Fully registered: no need to resume
    try:
        is_full = await sync_to_async(lambda: getattr(student, 'is_fully_registered', False))()
        if is_full:
            return None, {}
    except Exception:
        pass

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

    # Build state_data from DB for continuation messages
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
        "guardian_name": _v(parent, "full_name") if parent else "",
        "guardian_relationship": _v(parent, "relationship") if parent else "",
        "guardian_phone": _v(parent, "phone_number") if parent else "",
        "guardian_phone2": _v(parent, "phone_number2") if parent else "",
        "teacher_name": _v(teacher, "full_name") if teacher else "",
        "teacher_workplace": _v(teacher, "workplace") if teacher else "",
        "teacher_phone": _v(teacher, "phone_number") if teacher else "",
        "source_type": getattr(source, "source_type", None) if source else "",
    }
    if getattr(student, "phone_owner", None):
        state_data["phone_owner"] = student.phone_owner

    # Stage 1
    if not state_data["initial_full_name"]:
        return "waiting_for_initial_full_name", state_data
    if not (student.phone_number and str(student.phone_number).strip()):
        return "waiting_for_initial_phone", state_data
    if not (getattr(student, "phone_owner", None) and str(student.phone_owner or "").strip()):
        return "waiting_for_phone_owner", state_data
    # Stage 1 done, Stage 2 not started (no first_name from olympiad form)
    if not state_data["first_name"]:
        return "waiting_for_olympiad_participation", state_data

    # Stage 2 steps
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
    
    elif current_state == RegistrationStates.waiting_for_first_name:
        await message.answer(PROMO_TEXT, reply_markup=get_olympiad_participation_keyboard())
        await state.set_state(RegistrationStates.waiting_for_olympiad_participation)
        
    elif current_state == RegistrationStates.waiting_for_last_name:
        await message.answer(STEP_1_ASK_NAME, reply_markup=get_back_reply_keyboard())
        await state.set_state(RegistrationStates.waiting_for_first_name)
        
    elif current_state == RegistrationStates.waiting_for_date_of_birth:
        first_name = data.get('first_name', '')
        await message.answer(STEP_2_ASK_SURNAME.format(first_name=first_name), reply_markup=get_back_reply_keyboard())
        await state.set_state(RegistrationStates.waiting_for_last_name)
        
    elif current_state == RegistrationStates.waiting_for_document_number:
        await message.answer(STEP_3_ASK_DOB, reply_markup=get_back_reply_keyboard())
        await state.set_state(RegistrationStates.waiting_for_date_of_birth)
        
    elif current_state == RegistrationStates.waiting_for_district:
        document_number = data.get('document_number', '')
        await message.answer(STEP_5_ASK_REGION.format(document_number=document_number), reply_markup=get_region_keyboard())
        await state.set_state(RegistrationStates.waiting_for_region)
        
    elif current_state == RegistrationStates.waiting_for_school_name:
        region = data.get('region', '')
        region_label = dict(Student.REGION_CHOICES).get(region, '')
        await message.answer(STEP_6_ASK_DISTRICT.format(region_label=region_label), reply_markup=get_back_reply_keyboard())
        await state.set_state(RegistrationStates.waiting_for_district)
        
    elif current_state == RegistrationStates.waiting_for_achievements_description:
        await message.answer(STEP_9_ASK_PHOTO)
        await state.set_state(RegistrationStates.waiting_for_photo)
        
    elif current_state == RegistrationStates.waiting_for_guardian_name:
        await message.answer(STEP_10_ASK_ACHIEVEMENTS, reply_markup=get_skip_keyboard())
        await state.set_state(RegistrationStates.waiting_for_achievements_description)
        
    elif current_state == RegistrationStates.waiting_for_guardian_phone:
        await message.answer(STEP_12_ASK_RELATIONSHIP, reply_markup=get_relationship_keyboard())
        await state.set_state(RegistrationStates.waiting_for_guardian_relationship)
        
    elif current_state == RegistrationStates.waiting_for_teacher_name:
        relation = data.get('guardian_relationship', '')
        relation_text = RELATION_SUFFIX_MAP.get(relation, 'Vasiyingiz')
        await message.answer(STEP_13_ASK_GUARDIAN_PHONE.format(relation_text=relation_text), reply_markup=get_back_reply_keyboard())
        await state.set_state(RegistrationStates.waiting_for_guardian_phone)
        
    elif current_state == RegistrationStates.waiting_for_teacher_phone:
        await message.answer(STEP_14_ASK_TEACHER_NAME, reply_markup=get_back_reply_keyboard())
        await state.set_state(RegistrationStates.waiting_for_teacher_name)
    
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
        await callback.message.delete()
        await callback.message.answer(STEP_INITIAL_PHONE, reply_markup=get_phone_keyboard())
        await state.set_state(RegistrationStates.waiting_for_initial_phone)
        
    elif current_state == RegistrationStates.waiting_for_olympiad_participation:
        await callback.message.delete()
        await callback.message.answer(STEP_PHONE_OWNER, reply_markup=get_phone_owner_keyboard())
        await state.set_state(RegistrationStates.waiting_for_phone_owner)
        
    elif current_state == RegistrationStates.waiting_for_region:
        date_str = data.get('date_of_birth', '')
        await callback.message.delete()
        await callback.message.answer(STEP_4_ASK_METRIKA.format(date_str=date_str), reply_markup=get_back_reply_keyboard())
        await state.set_state(RegistrationStates.waiting_for_document_number)
        
    elif current_state == RegistrationStates.waiting_for_grade:
        district = data.get('district', '')
        await callback.message.delete()
        await callback.message.answer(STEP_7_ASK_SCHOOL.format(district=district), reply_markup=get_back_reply_keyboard())
        await state.set_state(RegistrationStates.waiting_for_school_name)
        
    elif current_state == RegistrationStates.waiting_for_photo:
        school_name = data.get('school_name', '')
        await callback.message.delete()
        await callback.message.answer(STEP_8_ASK_GRADE.format(school_name=school_name), reply_markup=get_grade_keyboard())
        await state.set_state(RegistrationStates.waiting_for_grade)
        
    elif current_state == RegistrationStates.waiting_for_guardian_relationship:
        await callback.message.delete()
        await callback.message.answer(STEP_11_ASK_GUARDIAN_NAME, reply_markup=get_back_reply_keyboard())
        await state.set_state(RegistrationStates.waiting_for_guardian_name)
        
    elif current_state == RegistrationStates.waiting_for_source:
        await callback.message.delete()
        await callback.message.answer(STEP_15_ASK_TEACHER_PHONE, reply_markup=get_back_reply_keyboard())
        await state.set_state(RegistrationStates.waiting_for_teacher_phone)
        
    elif current_state == RegistrationStates.waiting_for_confirmation:
        await callback.message.delete()
        await callback.message.answer(STEP_16_ASK_SOURCE, reply_markup=get_source_type_keyboard())
        await state.set_state(RegistrationStates.waiting_for_source)

    elif current_state == RegistrationStates.waiting_for_post_reg_promo:
        # Determine origin (Other Grade vs No, Share)
        school_name = data.get('school_name')
        if school_name:
             # Back to Grade
             await callback.message.delete()
             await callback.message.answer(STEP_8_ASK_GRADE.format(school_name=school_name), reply_markup=get_grade_keyboard())
             await state.set_state(RegistrationStates.waiting_for_grade)
        else:
             # Back to Promo
             await callback.message.delete()
             await callback.message.answer(PROMO_TEXT, reply_markup=get_olympiad_participation_keyboard())
             await state.set_state(RegistrationStates.waiting_for_olympiad_participation)

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
        keyboard = _build_channel_keyboard(channels)
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
            await callback.message.answer(SUCCESS_MESSAGE)
            await callback.message.answer(MENU_PROMPT, reply_markup=get_main_menu_keyboard())
            await state.clear()
            await BotStateService.clear_state(telegram_id)
        elif after_channels == "other_grade":
            await callback.message.answer(OTHER_GRADE_PROMO_MESSAGE, reply_markup=get_post_reg_promo_keyboard())
            await state.set_state(RegistrationStates.waiting_for_post_reg_promo)
            await BotStateService.set_state(telegram_id, "waiting_for_post_reg_promo")
        else:
            await callback.message.answer(CHECK_SUBS_SUCCESS)
        return

    await callback.message.delete()
    await callback.message.answer(CHECK_SUBS_SUCCESS)
    await callback.answer(CHECK_SUBS_CONFIRMED_ANSWER)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command. Supports referral: /start REF_CODE. Channel join is asked at end of registration.
    If user is in the middle of registration, resume from that step."""
    telegram_id = message.from_user.id
    username = message.from_user.username
    ref_code = _parse_start_referral(message.text or "")

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

    # Get or create student
    student, created = await StudentService.get_or_create_student(telegram_id, username)

    # If we didn't resume from saved state, try to infer stopped step from DB (e.g. user sent /start again after losing state)
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
                if text is not None:
                    if inferred_state in WELCOME_VIDEO_STATES:
                        await _send_welcome_video_if_exists(message)
                    kwargs = {"reply_markup": reply_markup}
                    if text == REFERRAL_ONLY_PROMO_TEXT:
                        kwargs["link_preview_options"] = LinkPreviewOptions(is_disabled=True)
                    await message.answer(text, **kwargs)
                    return

    # 1. Send Video Note (if exists; retry once on failure)
    await _send_welcome_video_if_exists(message)

    if student.first_name and student.last_name and student.date_of_birth and student.document_number:
        # Student already fully registered (Stage 2 complete)
        await message.answer(
            ALREADY_REGISTERED.format(first_name=student.first_name),
            reply_markup=get_main_menu_keyboard()
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
        
        # Store referrer in state
        if ref_code and ref_code != str(telegram_id):
            referrer = await StudentService.get_student_by_referral_code(ref_code)
            if referrer and referrer.telegram_id != telegram_id:
                if referrer.first_name and referrer.last_name and referrer.document_number:
                    await BotStateService.update_state_data(telegram_id, referrer_telegram_id=referrer.telegram_id)


# ==================== STAGE 1: INITIAL REGISTRATION ====================

@router.message(StateFilter(RegistrationStates.waiting_for_initial_full_name))
async def process_initial_full_name(message: Message, state: FSMContext):
    """Process initial full name."""
    if not message.text:
        await message.answer(ERROR_NAME_LENGTH)
        return
        
    full_name = message.text.strip()
    if len(full_name) < 2:
        await message.answer(ERROR_NAME_LENGTH)
        return

    # Update state
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, initial_full_name=full_name)
    
    # Move to next step
    await state.set_state(RegistrationStates.waiting_for_initial_phone)
    await BotStateService.set_state(telegram_id, "waiting_for_initial_phone")
    
    await message.answer(STEP_INITIAL_PHONE, reply_markup=get_phone_keyboard())


@router.message(StateFilter(RegistrationStates.waiting_for_initial_phone))
async def process_initial_phone(message: Message, state: FSMContext):
    """Process initial phone number."""
    phone = None
    if message.contact:
        phone = message.contact.phone_number
    elif message.text:
        phone = message.text.strip()
    
    # Basic validation
    if not phone or len(phone) < 9: # Simple check
         await message.answer(ERROR_INVALID_PHONE_UZB)
         return

    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, initial_phone=phone)

    # Move to next step
    await state.set_state(RegistrationStates.waiting_for_phone_owner)
    await BotStateService.set_state(telegram_id, "waiting_for_phone_owner")

    await message.answer(STEP_PHONE_OWNER, reply_markup=get_phone_owner_keyboard())


@router.callback_query(StateFilter(RegistrationStates.waiting_for_phone_owner))
async def process_phone_owner(callback: CallbackQuery, state: FSMContext):
    """Process phone owner selection."""
    if not callback.data.startswith('phone_owner_'):
        await callback.answer(ERROR_USE_BUTTONS)
        return

    # Delete message
    await callback.message.delete()

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
    
    # Send Promo Question
    await callback.message.answer(PROMO_TEXT, reply_markup=get_olympiad_participation_keyboard())
    
    await state.set_state(RegistrationStates.waiting_for_olympiad_participation)
    await BotStateService.set_state(telegram_id, "waiting_for_olympiad_participation")


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
        await callback.answer(ERROR_NOT_REGISTERED)
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

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "referral_menu_back")
async def referral_menu_back(callback: CallbackQuery, state: FSMContext):
    """Show REFERRAL_DESC (link + points) when user clicks Ortga from referral menu."""
    telegram_id = callback.from_user.id
    student = await StudentService.get_student(telegram_id)
    if not student or not student.first_name:
        await callback.answer(ERROR_NOT_REGISTERED)
        return

    ref_code = student.referral_code or str(telegram_id)
    bot_me = await callback.bot.get_me()
    bot_username = bot_me.username if bot_me else ""
    referral_link = f"https://t.me/{bot_username}?start={ref_code}" if bot_username else ""
    text = REFERRAL_DESC.format(referral_link=referral_link)

    await callback.message.edit_text(text)
    await callback.answer()


@router.message(F.text == "🏆 Reyting")
async def handle_leaderboard(message: Message, state: FSMContext):
    """Show referral leaderboard."""
    telegram_id = message.from_user.id
    student = await StudentService.get_student(telegram_id)
    if not student or not student.first_name:
        await message.answer(ERROR_NOT_REGISTERED)
        return

    leaderboard = await StudentService.get_referral_leaderboard(limit=10)
    text = LEADERBOARD_TITLE

    if leaderboard:
        for i, row in enumerate(leaderboard, 1):
            name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip() or "—"
            pts = row.get('referral_points') or 0
            if row.get('telegram_id') == telegram_id:
                name = f"<b>{name}</b>"
            text += f"{i}. {name} — <b>{pts}</b> ball\n"
    else:
        text += LEADERBOARD_EMPTY

    rank = await StudentService.get_user_referral_rank(telegram_id)
    if rank is not None and rank > 10:
        text += "\n____\n\n"
        user_points = getattr(student, 'referral_points', 0) or 0
        text += LEADERBOARD_USER_RANK.format(rank=rank, user_points=user_points)

    await message.answer(text)


# ==================== STEP 1: NAME ====================

@router.message(StateFilter(RegistrationStates.waiting_for_first_name))
async def process_first_name(message: Message, state: FSMContext):
    """Process first name."""
    if not message.text:
        await message.answer(ERROR_NAME_LENGTH)
        return
    
    first_name = message.text.strip()
    
    if len(first_name) < 2:
        await message.answer(ERROR_NAME_LENGTH)
        return
    
    telegram_id = message.from_user.id
    await StudentService.update_student(telegram_id, first_name=first_name)
    await BotStateService.update_state_data(telegram_id, first_name=first_name)
    
    await message.answer(STEP_2_ASK_SURNAME.format(first_name=first_name), reply_markup=get_back_reply_keyboard())
    await state.set_state(RegistrationStates.waiting_for_last_name)


# ==================== STEP 2: SURNAME ====================

@router.message(StateFilter(RegistrationStates.waiting_for_last_name))
async def process_last_name(message: Message, state: FSMContext):
    """Process last name."""
    last_name = message.text.strip() if message.text else None
    
    if not last_name or len(last_name) < 2:
        await message.answer(ERROR_SURNAME_LENGTH)
        return
    
    telegram_id = message.from_user.id
    await StudentService.update_student(telegram_id, last_name=last_name)
    await BotStateService.update_state_data(telegram_id, last_name=last_name)
    
    await message.answer(STEP_3_ASK_DOB, reply_markup=get_back_reply_keyboard())
    # Skipping Middle Name, going to DOB
    await state.set_state(RegistrationStates.waiting_for_date_of_birth)


# ==================== STEP 3: DOB ====================

@router.message(StateFilter(RegistrationStates.waiting_for_date_of_birth))
async def process_date_of_birth(message: Message, state: FSMContext):
    """Process date of birth."""
    if not message.text:
        await message.answer(ERROR_DATE_FORMAT)
        return
    
    date_str = message.text.strip()
    
    try:
        # Changed format to DD-MM-YYYY
        date_of_birth = datetime.strptime(date_str, "%d-%m-%Y").date()
    except ValueError:
        await message.answer(ERROR_DATE_FORMAT)
        return
    
    telegram_id = message.from_user.id
    await StudentService.update_student(telegram_id, date_of_birth=date_of_birth)
    await BotStateService.update_state_data(telegram_id, date_of_birth=str(date_of_birth))
    
    await message.answer(STEP_4_ASK_METRIKA.format(date_str=date_str), reply_markup=get_back_reply_keyboard())
    await state.set_state(RegistrationStates.waiting_for_document_number)


# ==================== STEP 4: METRIKA ====================

@router.message(StateFilter(RegistrationStates.waiting_for_document_number))
async def process_document_number(message: Message, state: FSMContext):
    """Process document number."""
    if not message.text:
        await message.answer("Iltimos, tug'ilganlik haqidagi guvohnoma raqamini kiriting.")
        return
    
    document_number = message.text.strip()
    
    telegram_id = message.from_user.id
    await StudentService.update_student(telegram_id, document_number=document_number)
    await BotStateService.update_state_data(telegram_id, document_number=document_number)
    
    await message.answer(
        STEP_5_ASK_REGION.format(document_number=document_number),
        reply_markup=get_region_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_region)


# ==================== STEP 5: REGION ====================

@router.callback_query(StateFilter(RegistrationStates.waiting_for_region), F.data.startswith("region_"))
async def process_region(callback: CallbackQuery, state: FSMContext):
    """Process region selection."""
    region = callback.data.split("_", 1)[1]
    
    telegram_id = callback.from_user.id
    await StudentService.update_student(telegram_id, region=region)
    await BotStateService.update_state_data(telegram_id, region=region)
    
    region_label = dict(Student.REGION_CHOICES)[region]
    
    await callback.message.delete()
    await callback.message.answer(STEP_6_ASK_DISTRICT.format(region_label=region_label), reply_markup=get_back_reply_keyboard())
    await callback.answer()
    await state.set_state(RegistrationStates.waiting_for_district)


# ==================== STEP 6: DISTRICT ====================

@router.message(StateFilter(RegistrationStates.waiting_for_district))
async def process_district(message: Message, state: FSMContext):
    """Process district."""
    if not message.text:
        await message.answer("Iltimos, tuman nomini kiriting.")
        return
    
    district = message.text.strip()
    
    telegram_id = message.from_user.id
    await StudentService.update_student(telegram_id, district=district)
    await BotStateService.update_state_data(telegram_id, district=district)
    
    await message.answer(STEP_7_ASK_SCHOOL.format(district=district), reply_markup=get_back_reply_keyboard())
    await state.set_state(RegistrationStates.waiting_for_school_name)


# ==================== STEP 7: SCHOOL ====================

@router.message(StateFilter(RegistrationStates.waiting_for_school_name))
async def process_school_name(message: Message, state: FSMContext):
    """Process school name."""
    if not message.text:
        await message.answer("Iltimos, maktab nomini kiriting.")
        return
    
    school_name = message.text.strip()
    
    telegram_id = message.from_user.id
    await StudentService.update_student(telegram_id, school_name=school_name)
    await BotStateService.update_state_data(telegram_id, school_name=school_name)
    
    await message.answer(STEP_8_ASK_GRADE.format(school_name=school_name), reply_markup=get_grade_keyboard())
    await state.set_state(RegistrationStates.waiting_for_grade)


# ==================== STEP 8: GRADE ====================

@router.callback_query(StateFilter(RegistrationStates.waiting_for_grade), F.data.startswith("grade_"))
async def process_grade(callback: CallbackQuery, state: FSMContext):
    """Process grade selection."""
    if callback.data == "grade_other":
        await callback.answer()
        telegram_id = callback.from_user.id
        # 1. Send explanation message
        await callback.message.edit_text(
            OTHER_GRADE_MESSAGE,
            disable_web_page_preview=True,
            parse_mode=ParseMode.HTML
        )
        # 2. Wait 5 seconds
        await asyncio.sleep(5)
        # 3. Ask to join channels first (if any); after join show referral promo
        subscription_status = await SubscriptionService.check_subscription(callback.bot, telegram_id)
        if subscription_status['subscribed']:
            await callback.message.answer(OTHER_GRADE_PROMO_MESSAGE, reply_markup=get_post_reg_promo_keyboard())
            await state.set_state(RegistrationStates.waiting_for_post_reg_promo)
            await BotStateService.set_state(telegram_id, "waiting_for_post_reg_promo")
        else:
            await callback.message.answer(
                CHECK_SUBS_START,
                reply_markup=_build_channel_keyboard(subscription_status['missing_channels'])
            )
            await state.set_state(RegistrationStates.waiting_for_channels)
            await BotStateService.set_state(telegram_id, "waiting_for_channels")
            await BotStateService.update_state_data(telegram_id, after_channels="other_grade")
        return

    grade = int(callback.data.split("_")[1])
    
    telegram_id = callback.from_user.id
    await StudentService.update_student(telegram_id, grade=grade)
    await BotStateService.update_state_data(telegram_id, grade=grade)
    
    # Skip Language, go to Photo
    await callback.message.edit_text(STEP_9_ASK_PHOTO, reply_markup=get_back_keyboard())
    await callback.answer()
    await state.set_state(RegistrationStates.waiting_for_photo)


# ==================== STEP 9: LANGUAGE (SKIPPED) ====================
# Handlers removed/bypassed

# ==================== STEP 10: PHOTO ====================

@router.message(StateFilter(RegistrationStates.waiting_for_photo), F.photo)
async def process_photo(message: Message, state: FSMContext):
    """Process photo."""
    photo = message.photo[-1]  # Get highest quality
    telegram_id = message.from_user.id
    
    # Download and save photo
    from django.conf import settings
    from exam_bot_admin.webhook import bot
    import os
    
    file = await bot.get_file(photo.file_id)
    
    # Create media directory if not exists
    media_dir = os.path.join(settings.MEDIA_ROOT, 'students')
    os.makedirs(media_dir, exist_ok=True)
    
    # Save file
    file_path = os.path.join(media_dir, f"{telegram_id}_{photo.file_id}.jpg")
    await bot.download_file(file.file_path, file_path)
    
    # Update student with relative path
    relative_path = f"students/{telegram_id}_{photo.file_id}.jpg"
    await StudentService.update_student(telegram_id, photo=relative_path)
    await BotStateService.update_state_data(telegram_id, photo=relative_path)
    
    await message.answer(STEP_10_ASK_ACHIEVEMENTS, reply_markup=get_skip_keyboard())
    await state.set_state(RegistrationStates.waiting_for_achievements_description)


@router.message(StateFilter(RegistrationStates.waiting_for_photo))
async def process_photo_invalid(message: Message):
    """Handle invalid photo."""
    await message.answer(ERROR_INVALID_PHOTO)


# ==================== STEP 11: ACHIEVEMENTS ====================

@router.callback_query(StateFilter(RegistrationStates.waiting_for_achievements_description), F.data == "skip")
async def skip_achievements_description(callback: CallbackQuery, state: FSMContext):
    """Skip achievements description."""
    telegram_id = callback.from_user.id
    await StudentService.update_student(telegram_id, achievements_description=None)
    
    # Skip File, go to Guardian Name
    await callback.message.delete()
    await callback.message.answer(STEP_11_ASK_GUARDIAN_NAME, reply_markup=get_back_reply_keyboard())
    await callback.answer()
    await state.set_state(RegistrationStates.waiting_for_guardian_name)


@router.message(StateFilter(RegistrationStates.waiting_for_achievements_description))
async def process_achievements_description(message: Message, state: FSMContext):
    """Process achievements description."""
    achievements_description = message.text.strip() if message.text else None
    
    telegram_id = message.from_user.id
    await StudentService.update_student(telegram_id, achievements_description=achievements_description)
    await BotStateService.update_state_data(telegram_id, achievements_description=achievements_description)
    
    # Skip File, go to Guardian Name
    await message.answer(STEP_11_ASK_GUARDIAN_NAME, reply_markup=get_back_reply_keyboard())
    await state.set_state(RegistrationStates.waiting_for_guardian_name)


# ==================== STEP 12: ACHIEVEMENTS FILE (SKIPPED) ====================
# Handlers removed/bypassed

@router.callback_query(StateFilter(RegistrationStates.waiting_for_achievements_file), F.data == "skip")
async def skip_achievements_file(callback: CallbackQuery, state: FSMContext):
    """Skip achievements file."""
    telegram_id = callback.from_user.id
    await StudentService.update_student(telegram_id, achievements_file=None)
    
    await callback.message.delete()
    await callback.message.answer(STEP_13_ASK_GUARDIAN_NAME, reply_markup=get_back_reply_keyboard())
    await callback.answer()
    await state.set_state(RegistrationStates.waiting_for_guardian_name)


@router.message(StateFilter(RegistrationStates.waiting_for_achievements_file), F.photo | F.document)
async def process_achievements_file(message: Message, state: FSMContext):
    """Process achievements file."""
    telegram_id = message.from_user.id
    
    # Download and save file
    from django.conf import settings
    from exam_bot_admin.webhook import bot
    import os
    
    if message.photo:
        file_obj = message.photo[-1]
        file = await bot.get_file(file_obj.file_id)
        media_dir = os.path.join(settings.MEDIA_ROOT, 'students', 'achievements')
        os.makedirs(media_dir, exist_ok=True)
        file_path = os.path.join(media_dir, f"{telegram_id}_{file_obj.file_id}.jpg")
        await bot.download_file(file.file_path, file_path)
        relative_path = f"students/achievements/{telegram_id}_{file_obj.file_id}.jpg"
    elif message.document:
        file = await bot.get_file(message.document.file_id)
        media_dir = os.path.join(settings.MEDIA_ROOT, 'students', 'achievements')
        os.makedirs(media_dir, exist_ok=True)
        file_path = os.path.join(media_dir, f"{telegram_id}_{message.document.file_id}_{message.document.file_name}")
        await bot.download_file(file.file_path, file_path)
        relative_path = f"students/achievements/{telegram_id}_{message.document.file_id}_{message.document.file_name}"
    else:
        await message.answer(ERROR_INVALID_FILE)
        return
    
    await StudentService.update_student(telegram_id, achievements_file=relative_path)
    await BotStateService.update_state_data(telegram_id, achievements_file=relative_path)
    
    await message.answer(STEP_13_ASK_GUARDIAN_NAME)
    await state.set_state(RegistrationStates.waiting_for_guardian_name)


@router.message(StateFilter(RegistrationStates.waiting_for_achievements_file))
async def process_achievements_file_invalid(message: Message):
    """Handle invalid achievements file."""
    await message.answer(ERROR_INVALID_FILE_OR_SKIP, reply_markup=get_skip_keyboard())


# ==================== STEP 13: GUARDIAN NAME ====================

@router.message(StateFilter(RegistrationStates.waiting_for_guardian_name))
async def process_guardian_name(message: Message, state: FSMContext):
    """Process guardian name."""
    if not message.text:
        await message.answer("Iltimos, vasiy ismini kiriting.")
        return
    
    guardian_name = message.text.strip()
    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, guardian_name=guardian_name)
    
    await message.answer(
        STEP_12_ASK_RELATIONSHIP,
        reply_markup=get_relationship_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_guardian_relationship)


# ==================== STEP 14: GUARDIAN RELATIONSHIP ====================

RELATION_SUFFIX_MAP = {
    'ota': 'Otangiz',
    'ona': 'Onangiz',
    'aka': 'Akangiz',
    'opa': 'Opangiz',
    'buvi': 'Buvingiz',
    'bobo': 'Bobongiz',
    'vasiy': 'Vasiyingiz',
    'boshqa': 'Vasiyingiz',
}

@router.callback_query(StateFilter(RegistrationStates.waiting_for_guardian_relationship), F.data.startswith("relationship_"))
async def process_guardian_relationship(callback: CallbackQuery, state: FSMContext):
    """Process guardian relationship."""
    relationship = callback.data.split("_", 1)[1]
    
    telegram_id = callback.from_user.id
    await BotStateService.update_state_data(telegram_id, guardian_relationship=relationship)
    
    relationship_label = dict(Parent.RELATIONSHIP_CHOICES)[relationship]
    relation_text = RELATION_SUFFIX_MAP.get(relationship, 'Vasiyingiz')
    
    # Skip Age/Profession, go to Phone
    await callback.message.delete()
    await callback.message.answer(
        STEP_13_ASK_GUARDIAN_PHONE.format(relation_text=relation_text),
        reply_markup=get_back_reply_keyboard()
    )
    await callback.answer()
    await state.set_state(RegistrationStates.waiting_for_guardian_phone)


# ==================== STEP 15 & 16: GUARDIAN AGE/PROFESSION (SKIPPED) ====================
# Handlers removed/bypassed

# ==================== STEP 17: GUARDIAN PHONE 1 ====================

@router.message(StateFilter(RegistrationStates.waiting_for_guardian_age))
async def process_guardian_age(message: Message, state: FSMContext):
    """Process guardian age."""
    if not message.text:
        await message.answer(ERROR_INVALID_AGE)
        return
    
    try:
        age = int(message.text.strip())
        if age < 18 or age > 120:
            raise ValueError
    except ValueError:
        await message.answer(ERROR_INVALID_AGE)
        return

    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, guardian_age=age)

    state_data = await BotStateService.get_state(telegram_id)
    data = (state_data.state_data or {}) if state_data else {}
    relationship = data.get('guardian_relationship', 'vasiy')
    relation_text = RELATION_SUFFIX_MAP.get(relationship, 'Vasiyingiz')

    await message.answer(
        STEP_13_ASK_GUARDIAN_PHONE.format(relation_text=relation_text)
    )
    
    # Go to Step 16
    await state.set_state(RegistrationStates.waiting_for_guardian_profession)


# ==================== STEP 16: GUARDIAN PROFESSION ====================

@router.message(StateFilter(RegistrationStates.waiting_for_guardian_profession))
async def process_guardian_profession(message: Message, state: FSMContext):
    """Process guardian profession."""
    if not message.text:
        await message.answer("Iltimos, kasb nomini kiriting.")
        return
    
    profession = message.text.strip()
    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, guardian_profession=profession)
    
    state_data = await BotStateService.get_state(telegram_id)
    data = (state_data.state_data or {}) if state_data else {}
    relationship = data.get('guardian_relationship', 'vasiy')
    relation_text = RELATION_SUFFIX_MAP.get(relationship, 'Vasiyingiz')

    # from bot.keyboards import get_phone_keyboard
    await message.answer(
        STEP_13_ASK_GUARDIAN_PHONE.format(relation_text=relation_text)
    )
    await state.set_state(RegistrationStates.waiting_for_guardian_phone)


# ==================== STEP 17: GUARDIAN PHONE 1 ====================

@router.message(StateFilter(RegistrationStates.waiting_for_guardian_phone))
async def process_guardian_phone(message: Message, state: FSMContext):
    """Process guardian phone 1."""
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text.strip()
        # Validate Uzbekistan phone number regex
        import re
        # Regex for Uzbekistan phone numbers:
        # +998 followed by 9 digits
        # 998 followed by 9 digits
        # 9 digits (local format without code, we can assume +998)
        # Allows spaces, dashes, parens
        
        # Clean the number first
        clean_phone = re.sub(r'[^\d+]', '', phone)
        
        if not re.match(r'^(\+998|998)?\d{9}$', clean_phone):
            await message.answer(ERROR_INVALID_PHONE_UZB)
            return

        # Format consistently to +998...
        if len(clean_phone) == 9:
            phone = f"+998{clean_phone}"
        elif len(clean_phone) == 12 and clean_phone.startswith('998'):
            phone = f"+{clean_phone}"
        else:
            phone = clean_phone # Keep as entered if it matched +998...

    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, guardian_phone=phone)
    
    # Skip Phone 2, go to Teacher Name
    await message.answer(STEP_14_ASK_TEACHER_NAME, reply_markup=get_back_reply_keyboard())
    await state.set_state(RegistrationStates.waiting_for_teacher_name)


# ==================== STEP 18: GUARDIAN PHONE 2 (SKIPPED) ====================
# Handlers removed/bypassed

# ==================== STEP 19: TEACHER NAME ====================

@router.callback_query(StateFilter(RegistrationStates.waiting_for_guardian_phone2), F.data == "skip")
async def skip_guardian_phone2(callback: CallbackQuery, state: FSMContext):
    """Skip guardian phone 2."""
    telegram_id = callback.from_user.id
    await BotStateService.update_state_data(telegram_id, guardian_phone2=None)
    
    await callback.message.delete()
    await callback.message.answer(STEP_14_ASK_TEACHER_NAME, reply_markup=get_back_reply_keyboard())
    await callback.answer()
    await state.set_state(RegistrationStates.waiting_for_teacher_name)


@router.message(StateFilter(RegistrationStates.waiting_for_guardian_phone2))
async def process_guardian_phone2(message: Message, state: FSMContext):
    """Process guardian phone 2."""
    if not message.text:
        await message.answer(ERROR_INVALID_PHONE_UZB)
        return
    
    phone = message.text.strip()
    
    # Validate Uzbekistan phone number regex
    import re
    clean_phone = re.sub(r'[^\d+]', '', phone)
    
    if not re.match(r'^(\+998|998)?\d{9}$', clean_phone):
        await message.answer(ERROR_INVALID_PHONE_UZB)
        return

    # Format
    if len(clean_phone) == 9:
        phone = f"+998{clean_phone}"
    elif len(clean_phone) == 12 and clean_phone.startswith('998'):
        phone = f"+{clean_phone}"
    else:
        phone = clean_phone

    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, guardian_phone2=phone)
    
    await message.answer(STEP_14_ASK_TEACHER_NAME)
    await state.set_state(RegistrationStates.waiting_for_teacher_name)


# ==================== STEP 19: TEACHER NAME ====================

@router.message(StateFilter(RegistrationStates.waiting_for_teacher_name))
async def process_teacher_name(message: Message, state: FSMContext):
    """Process teacher name."""
    if not message.text:
        await message.answer("Iltimos, ustoz ismini kiriting.")
        return
    
    teacher_name = message.text.strip()
    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, teacher_name=teacher_name)
    
    # Skip Workplace, go to Phone
    await message.answer(STEP_15_ASK_TEACHER_PHONE, reply_markup=get_back_reply_keyboard())
    await state.set_state(RegistrationStates.waiting_for_teacher_phone)


# ==================== STEP 20: TEACHER WORKPLACE (SKIPPED) ====================
# Handlers removed/bypassed

# ==================== STEP 21: TEACHER PHONE ====================

@router.message(StateFilter(RegistrationStates.waiting_for_teacher_workplace))
async def process_teacher_workplace(message: Message, state: FSMContext):
    """Process teacher workplace."""
    if not message.text:
        await message.answer("Iltimos, ish joyini kiriting.")
        return
    
    workplace = message.text.strip()
    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, teacher_workplace=workplace)
    
    # from bot.keyboards import get_phone_keyboard
    await message.answer(
        STEP_15_ASK_TEACHER_PHONE
    )
    await state.set_state(RegistrationStates.waiting_for_teacher_phone)


# ==================== STEP 21: TEACHER PHONE ====================

@router.message(StateFilter(RegistrationStates.waiting_for_teacher_phone))
async def process_teacher_phone(message: Message, state: FSMContext):
    """Process teacher phone."""
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text.strip()
        # Validate Uzbekistan phone number regex
        import re
        clean_phone = re.sub(r'[^\d+]', '', phone)
        
        if not re.match(r'^(\+998|998)?\d{9}$', clean_phone):
            await message.answer(ERROR_INVALID_PHONE_UZB)
            return
        
        # Format
        if len(clean_phone) == 9:
            phone = f"+998{clean_phone}"
        elif len(clean_phone) == 12 and clean_phone.startswith('998'):
            phone = f"+{clean_phone}"
        else:
            phone = clean_phone
    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, teacher_phone=phone)
    
    await message.answer(
        STEP_16_ASK_SOURCE,
        reply_markup=get_source_type_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_source)


# ==================== STEP 22: SOURCE ====================

@router.callback_query(StateFilter(RegistrationStates.waiting_for_source), F.data.startswith("source_"))
async def process_source(callback: CallbackQuery, state: FSMContext):
    """Process source selection."""
    source_type = callback.data.split("_", 1)[1]
    
    telegram_id = callback.from_user.id
    await BotStateService.update_state_data(telegram_id, source_type=source_type)
    
    # Finish
    await save_all_data_and_show_confirmation(callback, state, telegram_id)


# ==================== CONFIRMATION ====================

async def save_all_data_and_show_confirmation(message_or_callback, state: FSMContext, telegram_id: int):
    """Save all collected data and show confirmation page."""
    # Get student
    student = await StudentService.get_student(telegram_id)
    
    # Get state data
    state_data = await BotStateService.get_state(telegram_id)
    data = (state_data.state_data or {}) if state_data else {}
    
    # Guardian Data
    guardian_name = data.get('guardian_name')
    guardian_relationship = data.get('guardian_relationship')
    guardian_age = data.get('guardian_age')
    guardian_profession = data.get('guardian_profession')
    guardian_phone = data.get('guardian_phone')
    guardian_phone2 = data.get('guardian_phone2')
    
    # Teacher Data
    teacher_name = data.get('teacher_name')
    teacher_workplace = data.get('teacher_workplace')
    teacher_phone = data.get('teacher_phone')
    
    # Source Data
    source_type = data.get('source_type')
    
    # Save Parent
    if guardian_name:
        # Check if parent exists
        try:
            parent = await sync_to_async(lambda: student.parent)()
        except:
            parent = None

        if parent:
            parent.full_name = guardian_name
            parent.relationship = guardian_relationship
            # parent.age = guardian_age
            # parent.profession = guardian_profession
            parent.phone_number = guardian_phone
            # parent.phone_number2 = guardian_phone2
            await sync_to_async(parent.save)()
        else:
            # Create
            try:
                await StudentService.create_parent(
                    student,
                    full_name=guardian_name,
                    relationship=guardian_relationship,
                    phone_number=guardian_phone,
                    # age=guardian_age,
                    # profession=guardian_profession,
                    # phone_number2=guardian_phone2
                )
            except Exception as e:
                logger.error(f"Error creating parent: {e}")
        
    # Save Teacher
    if teacher_name:
        try:
            teacher = await sync_to_async(lambda: student.teacher)()
        except:
            teacher = None
            
        if teacher:
            teacher.full_name = teacher_name
            # teacher.workplace = teacher_workplace
            teacher.phone_number = teacher_phone
            await sync_to_async(teacher.save)()
        else:
            try:
                await StudentService.create_teacher(
                    student,
                    full_name=teacher_name,
                    phone_number=teacher_phone
                    # workplace=teacher_workplace
                )
            except Exception as e:
                logger.error(f"Error creating teacher: {e}")

    # Save Source
    if source_type:
        try:
            source = await sync_to_async(lambda: student.registration_source)()
        except:
            source = None
            
        if source:
            source.source_type = source_type
            await sync_to_async(source.save)()
        else:
            await sync_to_async(RegistrationSource.objects.create)(
                student=student,
                source_type=source_type
            )

    # Re-fetch for display
    student = await StudentService.get_student(telegram_id)
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

    confirmation_text = _build_confirmation_text(student, parent, teacher, source)

    # Send confirmation message
    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(
            confirmation_text,
            reply_markup=get_confirmation_keyboard()
        )
        await message_or_callback.answer()
    else:
        await message_or_callback.answer(
            confirmation_text,
            reply_markup=get_confirmation_keyboard()
        )
    
    await state.set_state(RegistrationStates.waiting_for_confirmation)


@router.callback_query(StateFilter(RegistrationStates.waiting_for_confirmation), F.data == "confirm")
async def confirm_registration(callback: CallbackQuery, state: FSMContext):
    """Confirm registration. Then ask to join channels (if any); after join show success + menu."""
    telegram_id = callback.from_user.id
    subscription_status = await SubscriptionService.check_subscription(callback.bot, telegram_id)

    if subscription_status['subscribed']:
        await callback.message.edit_text(SUCCESS_MESSAGE)
        await callback.message.answer(MENU_PROMPT, reply_markup=get_main_menu_keyboard())
        await state.clear()
        await BotStateService.clear_state(telegram_id)
        await callback.answer()
        return

    await callback.message.edit_text(CHECK_SUBS_START, reply_markup=_build_channel_keyboard(subscription_status['missing_channels']))
    await state.set_state(RegistrationStates.waiting_for_channels)
    await BotStateService.set_state(telegram_id, "waiting_for_channels")
    await BotStateService.update_state_data(telegram_id, after_channels="full_reg")
    await callback.answer()


@router.callback_query(StateFilter(RegistrationStates.waiting_for_post_reg_promo), F.data == "accept_promo")
async def accept_referral_promo(callback: CallbackQuery, state: FSMContext):
    """Handle referral promo acceptance."""
    telegram_id = callback.from_user.id
    
    # Check referrer awarding logic
    state_data = await BotStateService.get_state(telegram_id)
    data = (state_data.state_data or {}) if state_data else {}
    referrer_telegram_id = data.get("referrer_telegram_id")
    
    student = await StudentService.get_student(telegram_id)

    # Clear state
    await state.clear()
    await BotStateService.clear_state(telegram_id)
    
    if referrer_telegram_id and student:
        referrer = await StudentService.get_student(referrer_telegram_id)
        if referrer:
            await StudentService.create_referral_and_award_points(referrer, student, points=5)
            referrer_name = f"{student.first_name} {student.last_name or ''}".strip()
            send_referral_notification(referrer_telegram_id, referrer_name, points_earned=5)

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
    
    await callback.message.answer(MENU_PROMPT, reply_markup=get_main_menu_keyboard())
    await callback.answer()


@router.callback_query(StateFilter(RegistrationStates.waiting_for_confirmation), F.data == "edit")
async def start_editing(callback: CallbackQuery, state: FSMContext):
    """Start editing fields."""
    await callback.message.edit_text(EDIT_TITLE, reply_markup=get_edit_fields_keyboard())
    await callback.answer()
    await state.set_state(RegistrationStates.waiting_for_edit_field)


@router.callback_query(StateFilter(RegistrationStates.waiting_for_edit_field), F.data.startswith("edit_field:"))
async def select_field_to_edit(callback: CallbackQuery, state: FSMContext):
    """Select field to edit."""
    field_name = callback.data.split(":", 1)[1]
    telegram_id = callback.from_user.id
    
    # Store which field we're editing
    await BotStateService.update_state_data(telegram_id, editing_field=field_name)
    
    suffix = EDIT_FIELD_SUFFIXES.get(field_name, "ma'lumot kiriting:")
    prompt = f"{EDIT_PROMPT_PREFIX} {suffix}"
    
    # Handle special cases that need keyboards
    if field_name == 'region':
        await callback.message.edit_text(prompt, reply_markup=get_region_keyboard())
    elif field_name == 'grade':
        await callback.message.edit_text(prompt, reply_markup=get_grade_keyboard())
    elif field_name == 'language':
        await callback.message.edit_text(prompt, reply_markup=get_language_keyboard())
    elif field_name in ['achievements_description', 'achievements_file', 'guardian_phone2']:
        await callback.message.edit_text(prompt, reply_markup=get_skip_keyboard())
    elif field_name == 'guardian_relationship':
        await callback.message.edit_text(prompt, reply_markup=get_relationship_keyboard())
    elif field_name == 'source':
        await callback.message.edit_text(prompt, reply_markup=get_source_type_keyboard())
    else:
        await callback.message.edit_text(prompt)
    
    await callback.answer()
    await state.set_state(RegistrationStates.editing_field)


@router.message(StateFilter(RegistrationStates.editing_field))
async def process_editing_field(message: Message, state: FSMContext):
    """Process editing field value."""
    telegram_id = message.from_user.id
    state_data = await BotStateService.get_state(telegram_id)
    editing_field = state_data.state_data.get('editing_field')
    
    # Common update logic based on field
    if editing_field == 'photo':
        if not message.photo:
            await message.answer(ERROR_INVALID_PHOTO)
            return
        # Process photo same as before
        photo = message.photo[-1]
        from django.conf import settings
        from exam_bot_admin.webhook import bot
        import os
        file = await bot.get_file(photo.file_id)
        media_dir = os.path.join(settings.MEDIA_ROOT, 'students')
        os.makedirs(media_dir, exist_ok=True)
        file_path = os.path.join(media_dir, f"{telegram_id}_{photo.file_id}.jpg")
        await bot.download_file(file.file_path, file_path)
        relative_path = f"students/{telegram_id}_{photo.file_id}.jpg"
        await StudentService.update_student(telegram_id, photo=relative_path)

    elif editing_field == 'achievements_file':
        if message.photo:
            file_obj = message.photo[-1]
            from django.conf import settings
            from exam_bot_admin.webhook import bot
            import os
            file = await bot.get_file(file_obj.file_id)
            media_dir = os.path.join(settings.MEDIA_ROOT, 'students', 'achievements')
            os.makedirs(media_dir, exist_ok=True)
            file_path = os.path.join(media_dir, f"{telegram_id}_{file_obj.file_id}.jpg")
            await bot.download_file(file.file_path, file_path)
            relative_path = f"students/achievements/{telegram_id}_{file_obj.file_id}.jpg"
            await StudentService.update_student(telegram_id, achievements_file=relative_path)
        else:
            await message.answer(ERROR_INVALID_PHOTO)
            return

    elif editing_field == 'date_of_birth':
        if not message.text:
            await message.answer(ERROR_DATE_FORMAT_EDIT)
            return
        try:
            date_of_birth = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
            await StudentService.update_student(telegram_id, date_of_birth=date_of_birth)
        except ValueError:
            await message.answer(ERROR_DATE_FORMAT_EDIT)
            return

    elif editing_field in ['grade', 'region', 'language', 'guardian_relationship', 'source']:
        await message.answer(ERROR_USE_BUTTONS)
        return
        
    elif editing_field == 'guardian_name':
        if not message.text:
            await message.answer("Iltimos, vasiy ismini kiriting.")
            return
        value = message.text.strip()
        await BotStateService.update_state_data(telegram_id, guardian_name=value)
        
    elif editing_field == 'guardian_age':
        if not message.text:
            await message.answer(ERROR_INVALID_AGE)
            return
        try:
            age = int(message.text.strip())
            if age < 18 or age > 120:
                raise ValueError
            await BotStateService.update_state_data(telegram_id, guardian_age=age)
        except ValueError:
            await message.answer(ERROR_INVALID_AGE)
            return

    elif editing_field == 'guardian_profession':
        if not message.text:
            await message.answer("Iltimos, kasb nomini kiriting.")
            return
        value = message.text.strip()
        await BotStateService.update_state_data(telegram_id, guardian_profession=value)

    elif editing_field == 'guardian_phone':
        if not message.text:
            await message.answer(ERROR_INVALID_PHONE_UZB)
            return
        value = message.text.strip()
        await BotStateService.update_state_data(telegram_id, guardian_phone=value)

    elif editing_field == 'guardian_phone2':
        if not message.text:
            await message.answer(ERROR_INVALID_PHONE_UZB)
            return
        value = message.text.strip()
        await BotStateService.update_state_data(telegram_id, guardian_phone2=value)

    elif editing_field == 'teacher_name':
        if not message.text:
            await message.answer("Iltimos, ustoz ismini kiriting.")
            return
        value = message.text.strip()
        await BotStateService.update_state_data(telegram_id, teacher_name=value)

    elif editing_field == 'teacher_workplace':
        value = message.text.strip()
        await BotStateService.update_state_data(telegram_id, teacher_workplace=value)

    elif editing_field == 'teacher_phone':
        value = message.text.strip()
        await BotStateService.update_state_data(telegram_id, teacher_phone=value)

    else:
        # Generic text fields
        value = message.text.strip()
        kwargs = {editing_field: value}
        await StudentService.update_student(telegram_id, **kwargs)
    
    await save_all_data_and_show_confirmation(message, state, telegram_id)


@router.callback_query(StateFilter(RegistrationStates.editing_field))
async def process_editing_callback(callback: CallbackQuery, state: FSMContext):
    """Process editing field callback (for region, grade, language)."""
    telegram_id = callback.from_user.id
    state_data = await BotStateService.get_state(telegram_id)
    editing_field = state_data.state_data.get('editing_field')
    
    if editing_field == 'region' and callback.data.startswith('region_'):
        value = callback.data.split('_', 1)[1]
        await StudentService.update_student(telegram_id, region=value)
    elif editing_field == 'grade' and callback.data.startswith('grade_'):
        value = int(callback.data.split('_')[1])
        await StudentService.update_student(telegram_id, grade=value)
    elif editing_field == 'language' and callback.data.startswith('language_'):
        value = callback.data.split('_')[1]
        await StudentService.update_student(telegram_id, language=value)
    elif editing_field == 'achievements_description' and callback.data == 'skip':
        await StudentService.update_student(telegram_id, achievements_description=None)
    elif editing_field == 'achievements_file' and callback.data == 'skip':
         await StudentService.update_student(telegram_id, achievements_file=None)
    elif editing_field == 'guardian_relationship' and callback.data.startswith('relationship_'):
        value = callback.data.split('_', 1)[1]
        await BotStateService.update_state_data(telegram_id, guardian_relationship=value)
    elif editing_field == 'guardian_phone2' and callback.data == 'skip':
        await BotStateService.update_state_data(telegram_id, guardian_phone2=None)
    elif editing_field == 'source' and callback.data.startswith('source_'):
        value = callback.data.split('_', 1)[1]
        await BotStateService.update_state_data(telegram_id, source_type=value)
    
    await save_all_data_and_show_confirmation(callback, state, telegram_id)


@router.callback_query(StateFilter(RegistrationStates.waiting_for_edit_field), F.data == "back_to_confirmation")
async def back_to_confirmation(callback: CallbackQuery, state: FSMContext):
    """Go back to confirmation."""
    telegram_id = callback.from_user.id
    await save_all_data_and_show_confirmation(callback, state, telegram_id)
