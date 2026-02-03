"""Registration handlers."""
import logging
from datetime import datetime
from typing import Any

from asgiref.sync import sync_to_async
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, Contact, InlineKeyboardMarkup, InlineKeyboardButton

from bot.states import RegistrationStates, FeedbackStates
from bot.keyboards import (
    get_grade_keyboard, get_region_keyboard, get_language_keyboard,
    get_main_menu_keyboard, get_confirmation_keyboard, get_edit_fields_keyboard,
    get_skip_keyboard, get_relationship_keyboard, get_source_type_keyboard,
    get_post_reg_promo_keyboard
)
from bot.services import StudentService, BotStateService, SubscriptionService
from admin_panel.models import Student, Parent, Teacher, RegistrationSource
from admin_panel.utils import send_referral_notification

logger = logging.getLogger(__name__)

router = Router()


def _parse_start_referral(message_text: str) -> str | None:
    """Parse /start payload: /start REF_CODE -> return REF_CODE or None."""
    if not message_text or not message_text.strip().startswith("/start"):
        return None
    parts = message_text.strip().split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else None


@router.callback_query(F.data == "check_subs")
async def check_subs(callback: CallbackQuery, state: FSMContext):
    """Check subscription callback."""
    telegram_id = callback.from_user.id
    subscription_status = await SubscriptionService.check_subscription(callback.bot, telegram_id)
    
    if not subscription_status['subscribed']:
        channels = subscription_status['missing_channels']
        keyboard = []
        for ch in channels:
            link = ch.channel_username
            if not link and ch.channel_id.startswith('@'):
                link = f"https://t.me/{ch.channel_id[1:]}"
            if not link:
                link = "https://t.me/"
            keyboard.append([InlineKeyboardButton(text=f"📢 {ch.title}", url=link)])
        
        keyboard.append([InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_subs")])
        
        try:
            await callback.message.edit_text(
                "❌ <b>Siz hali quyidagi kanallarga obuna bo'lmadingiz:</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        except Exception:
            await callback.message.answer(
                "❌ <b>Siz hali quyidagi kanallarga obuna bo'lmadingiz:</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        await callback.answer("❌ Obuna tasdiqlanmadi")
        return

    await callback.message.delete()
    await callback.message.answer("✅ <b>Obuna tasdiqlandi!</b>\n\n/start buyrug'ini bosing.")
    await callback.answer("✅ Obuna tasdiqlandi!")


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command. Supports referral: /start REF_CODE."""
    telegram_id = message.from_user.id

    # Check mandatory channels
    subscription_status = await SubscriptionService.check_subscription(message.bot, telegram_id)
    if not subscription_status['subscribed']:
        channels = subscription_status['missing_channels']
        keyboard = []
        for ch in channels:
            link = ch.channel_username
            if not link and ch.channel_id.startswith('@'):
                link = f"https://t.me/{ch.channel_id[1:]}"
            if not link:
                link = "https://t.me/"
            keyboard.append([InlineKeyboardButton(text=f"📢 {ch.title}", url=link)])
        
        keyboard.append([InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_subs")])
        
        await message.answer(
            "❌ <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        return

    username = message.from_user.username
    ref_code = _parse_start_referral(message.text or "")

    # Get or create student
    student, created = await StudentService.get_or_create_student(telegram_id, username)

    if student.first_name and student.last_name and student.date_of_birth and student.document_number:
        # Student already registered
        await message.answer(
            f"Assalomu alaykum, {student.first_name}!\n\n"
            "Siz allaqachon ro'yxatdan o'tgansiz. Quyidagi menyudan kerakli bo'limni tanlang:",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
    else:
        # Start registration
        # Updated Text: Intro
        await message.answer(
            "👋 Assalomu alaykum! Oldinda sizni olimpiadaga ishtirok etish uchun 23 ta qadamlik ro'yxatdan o'tish jarayoni kutib turibdi 🤭\n"
            "Har bir qadamda sizdan quyidagi ma'lumotlarni so'raymiz:\n\n"
            "1. O'zingiz haqingizda:\n"
            "• Ism\n"
            "• Familiya\n"
            "• Tug'ilgan sana\n"
            "• Metrika raqami\n"
            "• Viloyat\n"
            "• Tuman/shahar\n"
            "• Maktab\n"
            "• Sinf\n"
            "• O'qish tili\n"
            "• Foto\n\n"
            "2. Vasiyingiz haqida\n"
            "3. Ustozingiz haqida\n\n"
            "Boshladikmi 😉\n\n"
            "1-qadam: Ismingizni kiriting:"
        )
        await state.set_state(RegistrationStates.waiting_for_first_name)
        await BotStateService.set_state(telegram_id, "waiting_for_first_name")
        # Store referrer in state
        if ref_code and ref_code != str(telegram_id):
            referrer = await StudentService.get_student_by_referral_code(ref_code)
            if referrer and referrer.telegram_id != telegram_id:
                if referrer.first_name and referrer.last_name and referrer.document_number:
                    await BotStateService.update_state_data(telegram_id, referrer_telegram_id=referrer.telegram_id)


@router.message(F.text == "👥 Do'stlarni taklif qilish")
async def handle_referral_menu(message: Message, state: FSMContext):
    """Show referral stats, link and leaderboard (Uzbek)."""
    telegram_id = message.from_user.id
    student = await StudentService.get_student(telegram_id)
    if not student or not student.first_name or not student.document_number:
        await message.answer("❌ Avval ro'yxatdan o'ting!")
        return

    points = getattr(student, 'referral_points', 0) or 0
    ref_code = student.referral_code or str(telegram_id)
    bot_me = await message.bot.get_me()
    bot_username = bot_me.username if bot_me else ""
    referral_link = f"https://t.me/{bot_username}?start={ref_code}" if bot_username else ""

    text = (
        "👥 <b>Do'stlarni taklif qilish</b>\n\n"
        f"📊 <b>Sizning ballaringiz:</b> {points} ball\n\n"
        "Har bir sizning havolangiz orqali ro'yxatdan o'tgan do'stingiz uchun siz <b>5 ball</b> olasiz.\n\n"
        "<b>Sizning havolangiz:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        "Reytingni ko'rish uchun asosiy menyuda <b>🏆 Reyting</b> tugmasini bosing."
    )

    await message.answer(text)


@router.message(F.text == "🏆 Reyting")
async def handle_leaderboard(message: Message, state: FSMContext):
    """Show referral leaderboard."""
    telegram_id = message.from_user.id
    student = await StudentService.get_student(telegram_id)
    if not student or not student.first_name or not student.document_number:
        await message.answer("❌ Avval ro'yxatdan o'ting!")
        return

    leaderboard = await StudentService.get_referral_leaderboard(limit=10)
    text = "🏆 <b>Reyting</b> (referral ballari bo'yicha)\n\n"

    if leaderboard:
        for i, row in enumerate(leaderboard, 1):
            name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip() or "—"
            pts = row.get('referral_points') or 0
            if row.get('telegram_id') == telegram_id:
                name = f"<b>{name}</b>"
            text += f"{i}. {name} — <b>{pts}</b> ball\n"
    else:
        text += "Reyting hali bo'sh.\n"

    rank = await StudentService.get_user_referral_rank(telegram_id)
    if rank is not None and rank > 10:
        text += "\n____\n\n"
        user_points = getattr(student, 'referral_points', 0) or 0
        text += f"Sizning o'rningiz: <b>{rank}</b> — <b>{user_points}</b> ball"

    await message.answer(text)


# ==================== STEP 1: NAME ====================

@router.message(StateFilter(RegistrationStates.waiting_for_first_name))
async def process_first_name(message: Message, state: FSMContext):
    """Process first name."""
    first_name = message.text.strip()
    
    if len(first_name) < 2:
        await message.answer("❌ Iltimos, to'g'ri ism kiriting (kamida 2 ta belgi):")
        return
    
    telegram_id = message.from_user.id
    await StudentService.update_student(telegram_id, first_name=first_name)
    await BotStateService.update_state_data(telegram_id, first_name=first_name)
    
    # Updated Text: After Name -> Ask Surname
    await message.answer(
        f"Rahmat, {first_name} 🙌\n\n"
        "Navbat 2-qadamga: Familiyangizni kiriting:"
    )
    await state.set_state(RegistrationStates.waiting_for_last_name)


# ==================== STEP 2: SURNAME ====================

@router.message(StateFilter(RegistrationStates.waiting_for_last_name))
async def process_last_name(message: Message, state: FSMContext):
    """Process last name."""
    last_name = message.text.strip() if message.text else None
    
    if not last_name or len(last_name) < 2:
        await message.answer("❌ Iltimos, to'g'ri familiya kiriting (kamida 2 ta belgi):")
        return
    
    telegram_id = message.from_user.id
    await StudentService.update_student(telegram_id, last_name=last_name)
    await BotStateService.update_state_data(telegram_id, last_name=last_name)
    
    # Updated Text: After Surname -> Ask DOB
    await message.answer(
        "Familiyangiz ham muvaffaqiyatli saqlandi ✅\n\n"
        "Endi, 3-qadam: Qaysi sanada tug'ilgansiz? 😊\n\n"
        "Faqat bitta iltimos, tug'ilgan sanangizni YYYY-MM-DD formatida kiriting, ya'ni: 2010-05-15"
    )
    # Skipping Middle Name, going to DOB
    await state.set_state(RegistrationStates.waiting_for_date_of_birth)


# ==================== STEP 3: DOB ====================

@router.message(StateFilter(RegistrationStates.waiting_for_date_of_birth))
async def process_date_of_birth(message: Message, state: FSMContext):
    """Process date of birth."""
    date_str = message.text.strip()
    
    try:
        date_of_birth = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        await message.answer(
            "❌ Iltimos, to'g'ri formatda kiriting (YYYY-MM-DD):\n"
            "Masalan: 2010-05-15"
        )
        return
    
    telegram_id = message.from_user.id
    await StudentService.update_student(telegram_id, date_of_birth=date_of_birth)
    await BotStateService.update_state_data(telegram_id, date_of_birth=str(date_of_birth))
    
    # Updated Text: After DOB -> Ask Metrika
    await message.answer(
        "Tug'ilgan sanangiz chiroyli sana ekan-a? 🙂\n\n"
        f"✅ Muvaffaqiyatli saqlandi: {date_str}\n\n"
        "Endigi navbat, 4-qadam: Tug'ilganlik haqida guvohnomangizning raqamiga:"
    )
    await state.set_state(RegistrationStates.waiting_for_document_number)


# ==================== STEP 4: METRIKA ====================

@router.message(StateFilter(RegistrationStates.waiting_for_document_number))
async def process_document_number(message: Message, state: FSMContext):
    """Process document number."""
    document_number = message.text.strip()
    
    telegram_id = message.from_user.id
    await StudentService.update_student(telegram_id, document_number=document_number)
    await BotStateService.update_state_data(telegram_id, document_number=document_number)
    
    # Updated Text: After Metrika -> Ask Region
    await message.answer(
        f"✅ Metrika raqamingizni saqladik: <b>{document_number}</b>\n\n"
        "Bizda 5-qadam: Viloyatingizni belgilang:",
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
    
    # Updated Text: After Region -> Ask District
    await callback.message.edit_text(
        f"{region_label}danmisiz? 🙃 Ajoyib-ku 🔥\n\n"
        "6-qadamga ham yetib keldik: Qaysi tuman/shaharda istiqomat qilasiz?"
    )
    await callback.answer()
    await state.set_state(RegistrationStates.waiting_for_district)


# ==================== STEP 6: DISTRICT ====================

@router.message(StateFilter(RegistrationStates.waiting_for_district))
async def process_district(message: Message, state: FSMContext):
    """Process district."""
    district = message.text.strip()
    
    telegram_id = message.from_user.id
    await StudentService.update_student(telegram_id, district=district)
    await BotStateService.update_state_data(telegram_id, district=district)
    
    # Updated Text: After District -> Ask School
    await message.answer(
        f"{district} saqlandi ⭐️\n\n"
        "7-qadamga yetib keldik: Qaysi maktabda o'qiysiz? 🙃"
    )
    await state.set_state(RegistrationStates.waiting_for_school_name)


# ==================== STEP 7: SCHOOL ====================

@router.message(StateFilter(RegistrationStates.waiting_for_school_name))
async def process_school_name(message: Message, state: FSMContext):
    """Process school name."""
    school_name = message.text.strip()
    
    telegram_id = message.from_user.id
    await StudentService.update_student(telegram_id, school_name=school_name)
    await BotStateService.update_state_data(telegram_id, school_name=school_name)
    
    # Updated Text: After School -> Ask Grade
    await message.answer(
        f"8-qadam: {school_name}da nechanchi sinfsiz? 🙂",
        reply_markup=get_grade_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_grade)


# ==================== STEP 8: GRADE ====================

@router.callback_query(StateFilter(RegistrationStates.waiting_for_grade), F.data.startswith("grade_"))
async def process_grade(callback: CallbackQuery, state: FSMContext):
    """Process grade selection."""
    grade = int(callback.data.split("_")[1])
    
    telegram_id = callback.from_user.id
    await StudentService.update_student(telegram_id, grade=grade)
    await BotStateService.update_state_data(telegram_id, grade=grade)
    
    grade_label = dict(Student.GRADE_CHOICES)[grade]
    
    # Updated Text: After Grade -> Ask Language
    await callback.message.edit_text(
        "👉 9-qadamga navbat — O'qish tilingizni kiriting:",
        reply_markup=get_language_keyboard()
    )
    await callback.answer()
    await state.set_state(RegistrationStates.waiting_for_language)


# ==================== STEP 9: LANGUAGE ====================

@router.callback_query(StateFilter(RegistrationStates.waiting_for_language), F.data.startswith("language_"))
async def process_language(callback: CallbackQuery, state: FSMContext):
    """Process language selection."""
    language = callback.data.split("_")[1]
    
    telegram_id = callback.from_user.id
    await StudentService.update_student(telegram_id, language=language)
    await BotStateService.update_state_data(telegram_id, language=language)
    
    language_label = dict(Student.LANGUAGE_CHOICES)[language]
    
    # Updated Text: After Language -> Ask Photo
    await callback.message.edit_text(
        "✅ O'qish tilingiz saqlandi:\n\n"
        "Endi, 10-qadam: Rasmingizni yuboring 🖼"
    )
    await callback.answer()
    await state.set_state(RegistrationStates.waiting_for_photo)


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
    
    # Go to Step 11: Achievements
    await message.answer(
        "Rasmga gap yo'q 🔥\n\n"
        "11-qadamimiz biroz uzunroq:\n\n"
        "Avvalgi yutuqlaringiz haqida nima deyolasiz?\n\n"
        "(Yutuqlaringiz bo'lmasa, \"O'tkazib yuborish\" tugmasini bosishingiz mumkin)",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_achievements_description)


@router.message(StateFilter(RegistrationStates.waiting_for_photo))
async def process_photo_invalid(message: Message):
    """Handle invalid photo."""
    await message.answer("❌ Iltimos, rasm yuboring (foto yoki rasm fayl):")


# ==================== STEP 11: ACHIEVEMENTS ====================

@router.callback_query(StateFilter(RegistrationStates.waiting_for_achievements_description), F.data == "skip")
async def skip_achievements_description(callback: CallbackQuery, state: FSMContext):
    """Skip achievements description."""
    telegram_id = callback.from_user.id
    await StudentService.update_student(telegram_id, achievements_description=None)
    
    await callback.message.edit_text(
        "✅ Avvalgi yutuqlar o'tkazib yuborildi.\n"
        "12-qadamimizda yutuqlaringizning rasmini ham ulashib qo'ysangiz 👏",
        reply_markup=get_skip_keyboard()
    )
    await callback.answer()
    
    # Go to Step 12: Achievements File
    await state.set_state(RegistrationStates.waiting_for_achievements_file)


@router.message(StateFilter(RegistrationStates.waiting_for_achievements_description))
async def process_achievements_description(message: Message, state: FSMContext):
    """Process achievements description."""
    achievements_description = message.text.strip() if message.text else None
    
    telegram_id = message.from_user.id
    await StudentService.update_student(telegram_id, achievements_description=achievements_description)
    await BotStateService.update_state_data(telegram_id, achievements_description=achievements_description)
    
    await message.answer(
        "12-qadamimizda yutuqlaringizning rasmini ham ulashib qo'ysangiz 👏",
        reply_markup=get_skip_keyboard()
    )
    # Go to Step 12: Achievements File
    await state.set_state(RegistrationStates.waiting_for_achievements_file)


# ==================== STEP 12: ACHIEVEMENTS FILE ====================

@router.callback_query(StateFilter(RegistrationStates.waiting_for_achievements_file), F.data == "skip")
async def skip_achievements_file(callback: CallbackQuery, state: FSMContext):
    """Skip achievements file."""
    telegram_id = callback.from_user.id
    await StudentService.update_student(telegram_id, achievements_file=None)
    
    # Updated text and transition to Step 13
    await callback.message.edit_text(
        "✅ Avvalgi yutuqlar rasmi o'tkazib yuborildi.\n\n"
        "✅ 13-qadamga keldik:\n\n"
        "Endi vasiyingiz haqida ma'lumotlar so'raymiz 🙂\n\n"
        "Vasiyingiz to'liq ismlarini yozing:"
    )
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
        await message.answer("❌ Iltimos, fayl yoki rasm yuboring:")
        return
    
    await StudentService.update_student(telegram_id, achievements_file=relative_path)
    await BotStateService.update_state_data(telegram_id, achievements_file=relative_path)
    
    # Transition to Step 13
    await message.answer(
        "✅ 13-qadamga keldik:\n\n"
        "Endi vasiyingiz haqida ma'lumotlar so'raymiz 🙂\n\n"
        "Vasiyingiz to'liq ismlarini yozing:"
    )
    await state.set_state(RegistrationStates.waiting_for_guardian_name)


@router.message(StateFilter(RegistrationStates.waiting_for_achievements_file))
async def process_achievements_file_invalid(message: Message):
    """Handle invalid achievements file."""
    await message.answer(
        "❌ Iltimos, fayl yoki rasm yuboring yoki 'O'tkazib yuborish' tugmasini bosing:",
        reply_markup=get_skip_keyboard()
    )


# ==================== STEP 13: GUARDIAN NAME ====================

@router.message(StateFilter(RegistrationStates.waiting_for_guardian_name))
async def process_guardian_name(message: Message, state: FSMContext):
    """Process guardian name."""
    guardian_name = message.text.strip()
    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, guardian_name=guardian_name)
    
    await message.answer(
        f"✅ Vasiy ismi saqlandi: <b>{guardian_name}</b>\n\n"
        "✅ 14-qadam: Kiritilgan vasiy sizga kim? 🙃",
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
    
    # Prepare text for Step 15
    relation_text = RELATION_SUFFIX_MAP.get(relationship, 'Vasiyingiz')
    
    await callback.message.edit_text(
        f"✅ Vasiy kimligi saqlandi: <b>{relationship_label}</b>\n\n"
        f"15-qadam: {relation_text} nechi yoshdalar? 🙂"
    )
    await callback.answer()
    
    # Go to Step 15
    await state.set_state(RegistrationStates.waiting_for_guardian_age)


# ==================== STEP 15: GUARDIAN AGE ====================

@router.message(StateFilter(RegistrationStates.waiting_for_guardian_age))
async def process_guardian_age(message: Message, state: FSMContext):
    """Process guardian age."""
    try:
        age = int(message.text.strip())
        if age < 18 or age > 120:
            raise ValueError
    except ValueError:
        await message.answer("❌ Iltimos, to'g'ri yosh kiriting (18-120):")
        return
    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, guardian_age=age)
    
    # RELATION_SUFFIX_MAP needs to be accessible here or re-defined/imported if used, 
    # but for profession text we can use generic or from state.
    # Let's get relationship to make it nicer if possible, but simplest is generic.
    state_data = await BotStateService.get_state(telegram_id)
    data = (state_data.state_data or {}) if state_data else {}
    relationship = data.get('guardian_relationship', 'vasiy')
    relation_text = RELATION_SUFFIX_MAP.get(relationship, 'Vasiyingiz')

    await message.answer(
        f"✅ Vasiy yoshi saqlandi: <b>{age}</b>\n\n"
        f"16-qadam: {relation_text} nima ish qiladilar? Kasblari nima?"
    )
    
    # Go to Step 16
    await state.set_state(RegistrationStates.waiting_for_guardian_profession)


# ==================== STEP 16: GUARDIAN PROFESSION ====================

@router.message(StateFilter(RegistrationStates.waiting_for_guardian_profession))
async def process_guardian_profession(message: Message, state: FSMContext):
    """Process guardian profession."""
    profession = message.text.strip()
    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, guardian_profession=profession)
    
    state_data = await BotStateService.get_state(telegram_id)
    data = (state_data.state_data or {}) if state_data else {}
    relationship = data.get('guardian_relationship', 'vasiy')
    relation_text = RELATION_SUFFIX_MAP.get(relationship, 'Vasiyingiz')

    # from bot.keyboards import get_phone_keyboard
    await message.answer(
        f"✅ Kasblari saqlandi: <b>{profession}</b>\n\n"
        f"17-qadam: {relation_text}ning telefon raqamini kirita olasizmi? 👇"
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
             await message.answer(
                "❌ Iltimos, to'g'ri O'zbekiston telefon raqamini kiriting:\n"
                "Masalan: +998901234567 yoki 901234567"
            )
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
    
    await message.answer(
        f"✅ Telefon raqam saqlandi: <b>{phone}</b>\n\n"
        "18-qadam: Agar bo'lsa, 2-raqamlarini ham kiritsangiz, bo'lmasa o'tkazib yuborishingiz mumkin 🙂",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_guardian_phone2)


# ==================== STEP 18: GUARDIAN PHONE 2 ====================

@router.callback_query(StateFilter(RegistrationStates.waiting_for_guardian_phone2), F.data == "skip")
async def skip_guardian_phone2(callback: CallbackQuery, state: FSMContext):
    """Skip guardian phone 2."""
    telegram_id = callback.from_user.id
    await BotStateService.update_state_data(telegram_id, guardian_phone2=None)
    
    # Updated text and transition to Step 13
    await callback.message.edit_text(
        "✅ 2-raqam o'tkazib yuborildi.\n\n"
        "✅ 19-qadamga keldik:\n\n"
        "Endi ustozingiz haqida ma'lumotlar so'raymiz 🙂\n\n"
        "Ustozingiz to'liq ismlarini yozing:"
    )
    await callback.answer()
    await state.set_state(RegistrationStates.waiting_for_teacher_name)


@router.message(StateFilter(RegistrationStates.waiting_for_guardian_phone2))
async def process_guardian_phone2(message: Message, state: FSMContext):
    """Process guardian phone 2."""
    phone = message.text.strip()
    
    # Validate Uzbekistan phone number regex
    import re
    clean_phone = re.sub(r'[^\d+]', '', phone)
    
    if not re.match(r'^(\+998|998)?\d{9}$', clean_phone):
            await message.answer(
            "❌ Iltimos, to'g'ri O'zbekiston telefon raqamini kiriting:\n"
            "Masalan: +998901234567 yoki 901234567"
        )
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
    
    await message.answer(
        f"✅ 2-raqam saqlandi: <b>{phone}</b>\n\n"
        "✅ 19-qadamga keldik:\n\n"
        "Endi ustozingiz haqida ma'lumotlar so'raymiz 🙂\n\n"
        "Ustozingiz to'liq ismlarini yozing:"
    )
    await state.set_state(RegistrationStates.waiting_for_teacher_name)


# ==================== STEP 19: TEACHER NAME ====================

@router.message(StateFilter(RegistrationStates.waiting_for_teacher_name))
async def process_teacher_name(message: Message, state: FSMContext):
    """Process teacher name."""
    teacher_name = message.text.strip()
    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, teacher_name=teacher_name)
    
    await message.answer(
        f"✅ Ustoz ismi saqlandi: <b>{teacher_name}</b>\n\n"
        "✅ 20-qadam: Qayerda ishlaydilar 🙃"
    )
    await state.set_state(RegistrationStates.waiting_for_teacher_workplace)


# ==================== STEP 20: TEACHER WORKPLACE ====================

@router.message(StateFilter(RegistrationStates.waiting_for_teacher_workplace))
async def process_teacher_workplace(message: Message, state: FSMContext):
    """Process teacher workplace."""
    workplace = message.text.strip()
    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, teacher_workplace=workplace)
    
    # from bot.keyboards import get_phone_keyboard
    await message.answer(
        f"✅ Ish joyi saqlandi: <b>{workplace}</b>\n\n"
        "📞 21-qadam: Telefon raqamlarini yozsangiz"
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
             await message.answer(
                "❌ Iltimos, to'g'ri O'zbekiston telefon raqamini kiriting:\n"
                "Masalan: +998901234567 yoki 901234567"
            )
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
        f"✅ Ustoz raqami saqlandi: <b>{phone}</b>\n\n"
        "🙌 Oxiridan 1 ta oldingi qadamdamiz — 22-qadam:\n\n"
        "Olimpiadamiz haqida qayerdan eshitdingiz? 🙃",
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
            parent.age = guardian_age
            parent.profession = guardian_profession
            parent.phone_number = guardian_phone
            parent.phone_number2 = guardian_phone2
            await sync_to_async(parent.save)()
        else:
            await StudentService.create_parent(
                student,
                full_name=guardian_name,
                relationship=guardian_relationship,
                age=guardian_age,
                profession=profession if 'profession' in locals() else guardian_profession, # handle scope
                phone_number=guardian_phone,
                phone_number2=guardian_phone2
            )
            # Fix: create_parent might not accept all args if not updated in service, 
            # so safest is create then update or ensure service supports it. 
            # Let's assume standard django create or service method.
            # Actually StudentService.create_parent might be custom.
            # Let's do raw create for safety if service is limited, or update after create.
            if not parent:
                 # Re-fetch
                 try:
                    parent = await sync_to_async(lambda: student.parent)()
                 except:
                    pass
            if parent:
                parent.profession = guardian_profession
                parent.phone_number = guardian_phone
                parent.phone_number2 = guardian_phone2
                await sync_to_async(parent.save)()
        
    # Save Teacher
    if teacher_name:
        try:
            teacher = await sync_to_async(lambda: student.teacher)()
        except:
            teacher = None
            
        if teacher:
            teacher.full_name = teacher_name
            teacher.workplace = teacher_workplace
            teacher.phone_number = teacher_phone
            await sync_to_async(teacher.save)()
        else:
            await StudentService.create_teacher(
                student,
                full_name=teacher_name
            )
            # Update fields
            try:
                teacher = await sync_to_async(lambda: student.teacher)()
                teacher.workplace = teacher_workplace
                teacher.phone_number = teacher_phone
                await sync_to_async(teacher.save)()
            except:
                pass

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
    student = await StudentService.get_student(telegram_id) # Refresh
    try:
        parent = await sync_to_async(lambda: student.parent)()
    except:
        parent = None
    try:
        teacher = await sync_to_async(lambda: student.teacher)()
    except:
        teacher = None
    try:
        source = await sync_to_async(lambda: student.registration_source)()
    except:
        source = None

    # Build confirmation message
    confirmation_text = "🥳 Nihoyat, eng so'nggi qadam:\n\n"
    confirmation_text += "📝 Ushbu ma'lumotlarni tasdiqlaysizmi? 👇\n\n"
    
    confirmation_text += "<b>📋 O'quvchi ma'lumotlari:</b>\n"
    confirmation_text += f"• Ism: {student.first_name}\n"
    confirmation_text += f"• Familiya: {student.last_name or '—'}\n"
    confirmation_text += f"• Tug'ilgan sana: {student.date_of_birth or '—'}\n"
    confirmation_text += f"• Metrika: {student.document_number or '—'}\n"
    confirmation_text += f"• Viloyat: {dict(Student.REGION_CHOICES).get(student.region, '—')}\n"
    confirmation_text += f"• Tuman/shahar: {student.district or '—'}\n"
    confirmation_text += f"• Maktab: {student.school_name or '—'}\n"
    confirmation_text += f"• Sinf: {dict(Student.GRADE_CHOICES).get(student.grade, '—')}\n"
    confirmation_text += f"• Til: {dict(Student.LANGUAGE_CHOICES).get(student.language, '—')}\n"
    confirmation_text += f"• Foto: {'✅ Yuklangan' if student.photo else '❌'}\n"
    confirmation_text += f"• Yutuqlar: {student.achievements_description or 'Yo\'q'}\n"
    confirmation_text += f"• Yutuq rasmi: {'✅ Yuklangan' if student.achievements_file else '❌'}\n\n"
    
    confirmation_text += "<b>👤 Vasiy ma'lumotlari:</b>\n"
    if parent:
        confirmation_text += f"• Ism: {parent.full_name}\n"
        confirmation_text += f"• Kimligi: {dict(Parent.RELATIONSHIP_CHOICES).get(parent.relationship, '—')}\n"
        confirmation_text += f"• Yoshi: {parent.age or '—'}\n"
        confirmation_text += f"• Kasbi: {parent.profession or '—'}\n"
        confirmation_text += f"• Tel 1: {parent.phone_number or '—'}\n"
        confirmation_text += f"• Tel 2: {parent.phone_number2 or '—'}\n\n"
    else:
        confirmation_text += "Kiritilmadi\n\n"
        
    confirmation_text += "<b>🧑‍🏫 Ustoz ma'lumotlari:</b>\n"
    if teacher:
        confirmation_text += f"• Ism: {teacher.full_name}\n"
        confirmation_text += f"• Ish joyi: {teacher.workplace or '—'}\n"
        confirmation_text += f"• Tel: {teacher.phone_number or '—'}\n\n"
    else:
        confirmation_text += "Kiritilmadi\n\n"

    confirmation_text += "<b>📊 Manba:</b>\n"
    if source:
        confirmation_text += f"• {dict(RegistrationSource.SOURCE_TYPE_CHOICES).get(source.source_type, '—')}\n"
    else:
        confirmation_text += "Kiritilmadi\n"
    
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
    """Confirm registration."""
    telegram_id = callback.from_user.id
    
    # Send Success Message
    await callback.message.edit_text(
        "✅ Rasman! Siz Rahimov Matematika Olimpiadasi ishtirokchisisiz! 🔥\n\n"
        "Bu hali hammasi emas! Sizga olimpiadamiz tomonidan eksklyuziv taklif bor: Olimpiadaga tengdoshlaringizni taklif qiling. Eng ko'p taklif qilgan n ta o'rin sohibiga quyidagi sovg'alarni va'da qilamiz:\n\n"
        "🥇 1-o'rin: N\n"
        "🥈 2-o'rin: N\n"
        "🥉 3-o'ring: N\n"
        "...\n"
        "🎖 N-o'rin: N\n\n"
        "Har bir sizning havolangiz orqali ro'yxatdan o'tgan do'stingiz uchun 5 ball olasiz 🤩\n\n"
        "Rozi bo'lsangiz, \"Ha 🔥\" tugmasini bosing. Biz do'stlaringizga yuborishingiz kerak bo'lgan tayyor xabarni yuboramiz ⚡"
    )
    from bot.keyboards import get_post_reg_promo_keyboard
    await callback.message.edit_reply_markup(reply_markup=get_post_reg_promo_keyboard())
    
    await state.set_state(RegistrationStates.waiting_for_post_reg_promo)
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
    
    promo_text = (
        "👋 Assalomu alaykum! Sovg'asiga: N N N qo'yilgan \"Rahimov Matematika Olimpiadasi\"da qatnashishni istaysizmi?\n\n"
        "Men ro'yxatdan o'tdim ✅ Va tayyorlanishni boshlayapman 🙂\n"
        "Olimpiadaga haqida batafsil: [link]\n\n"
        f"Siz ham quyidagi havola orqali ro'yxatdan o'ting: {referral_link}"
    )
    
    # Send promo image with text
    from aiogram.types import FSInputFile
    import os
    from django.conf import settings
    
    photo_path = os.path.join(settings.MEDIA_ROOT, 'rmo_logo.jpg')
    
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(photo, caption=promo_text)
        await callback.message.delete() # Delete the previous text message to avoid clutter
    else:
        await callback.message.edit_text(promo_text)
    
    await callback.message.answer(
        "Quyidagi menyudan kerakli bo'limni tanlang:",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(StateFilter(RegistrationStates.waiting_for_confirmation), F.data == "edit")
async def start_editing(callback: CallbackQuery, state: FSMContext):
    """Start editing fields."""
    await callback.message.edit_text(
        "<b>✏️ Tahrirlash</b>\n\n"
        "Qaysi maydonni o'zgartirmoqchisiz?",
        reply_markup=get_edit_fields_keyboard()
    )
    await callback.answer()
    await state.set_state(RegistrationStates.waiting_for_edit_field)


@router.callback_query(StateFilter(RegistrationStates.waiting_for_edit_field), F.data.startswith("edit_field:"))
async def select_field_to_edit(callback: CallbackQuery, state: FSMContext):
    """Select field to edit."""
    field_name = callback.data.split(":", 1)[1]
    telegram_id = callback.from_user.id
    
    # Store which field we're editing
    await BotStateService.update_state_data(telegram_id, editing_field=field_name)
    
    # Map field names to prompts and states
    field_prompts = {
        'first_name': "Iltimos, yangi ism kiriting:",
        'last_name': "Iltimos, yangi familiya kiriting:",
        'date_of_birth': "Iltimos, yangi tug'ilgan sana kiriting (dd.mm.YYYY):",
        'document_number': "Iltimos, yangi metrika raqami kiriting:",
        'region': "Iltimos, yangi viloyat tanlang:",
        'district': "Iltimos, yangi tuman/shahar kiriting:",
        'school_name': "Iltimos, yangi maktab nomi kiriting:",
        'grade': "Iltimos, yangi sinf tanlang:",
        'language': "Iltimos, yangi o'qish tili tanlang:",
        'photo': "Iltimos, yangi rasm yuboring:",
        'achievements_description': "Iltimos, yangi avvalgi yutuqlar haqida yozing:",
        'achievements_file': "Iltimos, yangi yutuqlar rasmini yuboring:",
        'guardian_name': "Iltimos, yangi vasiy ismini kiriting:",
        'guardian_relationship': "Iltimos, yangi vasiy kimligini tanlang:",
        'guardian_age': "Iltimos, yangi vasiy yoshini kiriting:",
        'guardian_profession': "Iltimos, yangi vasiy kasbini kiriting:",
        'guardian_phone': "Iltimos, yangi vasiy telefonini kiriting:",
        'guardian_phone2': "Iltimos, yangi vasiy 2-telefonini kiriting:",
        'teacher_name': "Iltimos, yangi o'qituvchi ismini kiriting:",
        'teacher_workplace': "Iltimos, yangi o'qituvchi ish joyini kiriting:",
        'teacher_phone': "Iltimos, yangi o'qituvchi telefonini kiriting:",
        'source': "Iltimos, yangi manbani tanlang:",
    }
    
    prompt = field_prompts.get(field_name, "Iltimos, yangi ma'lumot kiriting:")
    
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
            await message.answer("❌ Iltimos, rasm yuboring:")
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
             await message.answer("❌ Iltimos, rasm yuboring:")
             return
    
    elif editing_field == 'date_of_birth':
        try:
            date_of_birth = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
            await StudentService.update_student(telegram_id, date_of_birth=date_of_birth)
        except ValueError:
            await message.answer("❌ Noto'g'ri sana formati. (dd.mm.YYYY)")
            return
    
    elif editing_field in ['grade', 'region', 'language', 'guardian_relationship', 'source']:
        await message.answer("❌ Iltimos, tugmalardan foydalaning.")
        return
        
    elif editing_field == 'guardian_name':
        value = message.text.strip()
        await BotStateService.update_state_data(telegram_id, guardian_name=value)
        
    elif editing_field == 'guardian_age':
        try:
            age = int(message.text.strip())
            if age < 18 or age > 120:
                raise ValueError
            await BotStateService.update_state_data(telegram_id, guardian_age=age)
        except ValueError:
             await message.answer("❌ Iltimos, to'g'ri yosh kiriting (18-120):")
             return

    elif editing_field == 'guardian_profession':
        value = message.text.strip()
        await BotStateService.update_state_data(telegram_id, guardian_profession=value)

    elif editing_field == 'guardian_phone':
        value = message.text.strip()
        await BotStateService.update_state_data(telegram_id, guardian_phone=value)

    elif editing_field == 'guardian_phone2':
        value = message.text.strip()
        await BotStateService.update_state_data(telegram_id, guardian_phone2=value)

    elif editing_field == 'teacher_name':
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
