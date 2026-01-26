"""Registration handlers."""
import logging
from datetime import datetime
from typing import Any

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, Contact

from bot.states import RegistrationStates
from bot.keyboards import (
    get_grade_keyboard, get_region_keyboard, get_language_keyboard,
    get_phone_keyboard, get_skip_keyboard, get_relationship_keyboard,
    get_source_type_keyboard, get_main_menu_keyboard, get_back_keyboard,
    get_confirmation_keyboard, get_edit_fields_keyboard, get_children_count_keyboard
)
from bot.services import StudentService, BotStateService
from admin_panel.models import Student, Parent, Teacher, RegistrationSource

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command."""
    telegram_id = message.from_user.id
    username = message.from_user.username
    
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
        await message.answer(
            "👋 <b>Assalomu alaykum!</b>\n\n"
            "Grant imtihon botiga xush kelibsiz!\n\n"
            "<b>Qadam-1: O'quvchi haqida</b>\n\n"
            "Majburiy ma'lumotlar:\n"
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
            "Keling, boshlaymiz! 👇\n\n"
            "<b>1-qadam:</b> Iltimos, ismingizni kiriting:"
        )
        await state.set_state(RegistrationStates.waiting_for_first_name)
        await BotStateService.set_state(telegram_id, "waiting_for_first_name")


# ==================== STEP 1: STUDENT INFORMATION ====================

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
    
    await message.answer(
        f"✅ Ism saqlandi: <b>{first_name}</b>\n\n"
        "<b>2-qadam:</b> Iltimos, familiyangizni kiriting:"
    )
    await state.set_state(RegistrationStates.waiting_for_last_name)


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
    
    await message.answer(
        f"✅ Familiya saqlandi: <b>{last_name}</b>\n\n"
        "<b>3-qadam:</b> Iltimos, sharifingizni kiriting:\n"
        "(Agar sharif bo'lmasa, 'O'tkazib yuborish' tugmasini bosing)",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_middle_name)


@router.callback_query(StateFilter(RegistrationStates.waiting_for_middle_name), F.data == "skip")
async def skip_middle_name(callback: CallbackQuery, state: FSMContext):
    """Skip middle name."""
    telegram_id = callback.from_user.id
    await StudentService.update_student(telegram_id, middle_name=None)
    
    await callback.message.edit_text(
        "✅ Sharif o'tkazib yuborildi.\n\n"
        "<b>4-qadam:</b> Iltimos, tug'ilgan sanangizni kiriting (YYYY-MM-DD formatida):\n"
        "Masalan: 2010-05-15"
    )
    await callback.answer()
    await state.set_state(RegistrationStates.waiting_for_date_of_birth)


@router.message(StateFilter(RegistrationStates.waiting_for_middle_name))
async def process_middle_name(message: Message, state: FSMContext):
    """Process middle name."""
    middle_name = message.text.strip() if message.text else None
    
    telegram_id = message.from_user.id
    await StudentService.update_student(telegram_id, middle_name=middle_name)
    await BotStateService.update_state_data(telegram_id, middle_name=middle_name)
    
    await message.answer(
        f"✅ Sharif saqlandi: <b>{middle_name or 'Kiritilmadi'}</b>\n\n"
        "<b>4-qadam:</b> Iltimos, tug'ilgan sanangizni kiriting (YYYY-MM-DD formatida):\n"
        "Masalan: 2010-05-15"
    )
    await state.set_state(RegistrationStates.waiting_for_date_of_birth)


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
    
    await message.answer(
        f"✅ Tug'ilgan sana saqlandi: <b>{date_of_birth}</b>\n\n"
        "<b>5-qadam:</b> Iltimos, metrika raqamingizni kiriting:"
    )
    await state.set_state(RegistrationStates.waiting_for_document_number)


@router.message(StateFilter(RegistrationStates.waiting_for_document_number))
async def process_document_number(message: Message, state: FSMContext):
    """Process document number."""
    document_number = message.text.strip()
    
    telegram_id = message.from_user.id
    await StudentService.update_student(telegram_id, document_number=document_number)
    await BotStateService.update_state_data(telegram_id, document_number=document_number)
    
    await message.answer(
        f"✅ Metrika raqami saqlandi: <b>{document_number}</b>\n\n"
        "<b>6-qadam:</b> Iltimos, viloyatingizni tanlang:",
        reply_markup=get_region_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_region)


@router.callback_query(StateFilter(RegistrationStates.waiting_for_region), F.data.startswith("region_"))
async def process_region(callback: CallbackQuery, state: FSMContext):
    """Process region selection."""
    region = callback.data.split("_", 1)[1]
    
    telegram_id = callback.from_user.id
    await StudentService.update_student(telegram_id, region=region)
    await BotStateService.update_state_data(telegram_id, region=region)
    
    region_label = dict(Student.REGION_CHOICES)[region]
    
    await callback.message.edit_text(
        f"✅ Viloyat saqlandi: <b>{region_label}</b>\n\n"
        "<b>7-qadam:</b> Iltimos, tuman/shaharingizni kiriting:"
    )
    await callback.answer()
    await state.set_state(RegistrationStates.waiting_for_district)


@router.message(StateFilter(RegistrationStates.waiting_for_district))
async def process_district(message: Message, state: FSMContext):
    """Process district."""
    district = message.text.strip()
    
    telegram_id = message.from_user.id
    await StudentService.update_student(telegram_id, district=district)
    await BotStateService.update_state_data(telegram_id, district=district)
    
    await message.answer(
        f"✅ Tuman/Shahar saqlandi: <b>{district}</b>\n\n"
        "<b>8-qadam:</b> Iltimos, maktab nomingizni kiriting:"
    )
    await state.set_state(RegistrationStates.waiting_for_school_name)


@router.message(StateFilter(RegistrationStates.waiting_for_school_name))
async def process_school_name(message: Message, state: FSMContext):
    """Process school name."""
    school_name = message.text.strip()
    
    telegram_id = message.from_user.id
    await StudentService.update_student(telegram_id, school_name=school_name)
    await BotStateService.update_state_data(telegram_id, school_name=school_name)
    
    await message.answer(
        f"✅ Maktab nomi saqlandi: <b>{school_name}</b>\n\n"
        "<b>9-qadam:</b> Iltimos, sinfingizni tanlang:",
        reply_markup=get_grade_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_grade)


@router.callback_query(StateFilter(RegistrationStates.waiting_for_grade), F.data.startswith("grade_"))
async def process_grade(callback: CallbackQuery, state: FSMContext):
    """Process grade selection."""
    grade = int(callback.data.split("_")[1])
    
    telegram_id = callback.from_user.id
    await StudentService.update_student(telegram_id, grade=grade)
    await BotStateService.update_state_data(telegram_id, grade=grade)
    
    grade_label = dict(Student.GRADE_CHOICES)[grade]
    
    await callback.message.edit_text(
        f"✅ Sinf saqlandi: <b>{grade_label}</b>\n\n"
        "<b>10-qadam:</b> Iltimos, o'qish tilini tanlang:",
        reply_markup=get_language_keyboard()
    )
    await callback.answer()
    await state.set_state(RegistrationStates.waiting_for_language)


@router.callback_query(StateFilter(RegistrationStates.waiting_for_language), F.data.startswith("language_"))
async def process_language(callback: CallbackQuery, state: FSMContext):
    """Process language selection."""
    language = callback.data.split("_")[1]
    
    telegram_id = callback.from_user.id
    await StudentService.update_student(telegram_id, language=language)
    await BotStateService.update_state_data(telegram_id, language=language)
    
    language_label = dict(Student.LANGUAGE_CHOICES)[language]
    
    await callback.message.edit_text(
        f"✅ O'qish tili saqlandi: <b>{language_label}</b>\n\n"
        "<b>11-qadam:</b> Iltimos, rasmingizni yuboring:"
    )
    await callback.answer()
    await state.set_state(RegistrationStates.waiting_for_photo)


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
    
    await message.answer(
        "✅ Rasm saqlandi!\n\n"
        "<b>12-qadam:</b> Iltimos, avvalgi yutuqlaringiz haqida izoh bering:\n"
        "(Agar yutuqlar bo'lmasa, 'O'tkazib yuborish' tugmasini bosing)",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_achievements_description)


@router.message(StateFilter(RegistrationStates.waiting_for_photo))
async def process_photo_invalid(message: Message):
    """Handle invalid photo."""
    await message.answer("❌ Iltimos, rasm yuboring (foto yoki rasm fayl):")


@router.callback_query(StateFilter(RegistrationStates.waiting_for_achievements_description), F.data == "skip")
async def skip_achievements_description(callback: CallbackQuery, state: FSMContext):
    """Skip achievements description."""
    telegram_id = callback.from_user.id
    await StudentService.update_student(telegram_id, achievements_description=None)
    
    await callback.message.edit_text(
        "✅ Avvalgi yutuqlar izohi o'tkazib yuborildi.\n\n"
        "<b>13-qadam:</b> Iltimos, avvalgi yutuqlaringiz faylini/rasmini yuboring:\n"
        "(Agar fayl bo'lmasa, 'O'tkazib yuborish' tugmasini bosing)",
        reply_markup=get_skip_keyboard()
    )
    await callback.answer()
    await state.set_state(RegistrationStates.waiting_for_achievements_file)


@router.message(StateFilter(RegistrationStates.waiting_for_achievements_description))
async def process_achievements_description(message: Message, state: FSMContext):
    """Process achievements description."""
    achievements_description = message.text.strip() if message.text else None
    
    telegram_id = message.from_user.id
    await StudentService.update_student(telegram_id, achievements_description=achievements_description)
    await BotStateService.update_state_data(telegram_id, achievements_description=achievements_description)
    
    await message.answer(
        f"✅ Avvalgi yutuqlar izohi saqlandi.\n\n"
        "<b>13-qadam:</b> Iltimos, avvalgi yutuqlaringiz faylini/rasmini yuboring:\n"
        "(Agar fayl bo'lmasa, 'O'tkazib yuborish' tugmasini bosing)",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_achievements_file)


@router.callback_query(StateFilter(RegistrationStates.waiting_for_achievements_file), F.data == "skip")
async def skip_achievements_file(callback: CallbackQuery, state: FSMContext):
    """Skip achievements file."""
    telegram_id = callback.from_user.id
    await StudentService.update_student(telegram_id, achievements_file=None)
    
    await callback.message.edit_text(
        "✅ Avvalgi yutuqlar fayli o'tkazib yuborildi.\n\n"
        "<b>Qadam-2: Vasiy haqida</b>\n\n"
        "<b>1-qadam:</b> Iltimos, vasiyning to'liq ismini kiriting (Ism, familiya):"
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
    
    await message.answer(
        "✅ Avvalgi yutuqlar fayli saqlandi!\n\n"
        "<b>Qadam-2: Vasiy haqida</b>\n\n"
        "<b>1-qadam:</b> Iltimos, vasiyning to'liq ismini kiriting (Ism, familiya):"
    )
    await state.set_state(RegistrationStates.waiting_for_guardian_name)


@router.message(StateFilter(RegistrationStates.waiting_for_achievements_file))
async def process_achievements_file_invalid(message: Message):
    """Handle invalid achievements file."""
    await message.answer("❌ Iltimos, fayl yoki rasm yuboring yoki 'O'tkazib yuborish' tugmasini bosing:", reply_markup=get_skip_keyboard())


# ==================== STEP 2: GUARDIAN INFORMATION ====================

@router.message(StateFilter(RegistrationStates.waiting_for_guardian_name))
async def process_guardian_name(message: Message, state: FSMContext):
    """Process guardian name."""
    guardian_name = message.text.strip()
    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, guardian_name=guardian_name)
    
    await message.answer(
        f"✅ Vasiy ismi saqlandi: <b>{guardian_name}</b>\n\n"
        "<b>2-qadam:</b> Iltimos, vasiyning kimligini tanlang:",
        reply_markup=get_relationship_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_guardian_relationship)


@router.callback_query(StateFilter(RegistrationStates.waiting_for_guardian_relationship), F.data.startswith("relationship_"))
async def process_guardian_relationship(callback: CallbackQuery, state: FSMContext):
    """Process guardian relationship."""
    relationship = callback.data.split("_", 1)[1]
    
    telegram_id = callback.from_user.id
    await BotStateService.update_state_data(telegram_id, guardian_relationship=relationship)
    
    relationship_label = dict(Parent.RELATIONSHIP_CHOICES)[relationship]
    
    await callback.message.edit_text(
        f"✅ Kimligi saqlandi: <b>{relationship_label}</b>\n\n"
        "<b>3-qadam:</b> Iltimos, vasiyning yoshini kiriting:"
    )
    await callback.answer()
    await state.set_state(RegistrationStates.waiting_for_guardian_age)


@router.message(StateFilter(RegistrationStates.waiting_for_guardian_age))
async def process_guardian_age(message: Message, state: FSMContext):
    """Process guardian age."""
    try:
        age = int(message.text.strip())
        if age < 1 or age > 150:
            raise ValueError
    except ValueError:
        await message.answer("❌ Iltimos, to'g'ri yosh kiriting (1-150):")
        return
    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, guardian_age=age)
    
    await message.answer(
        f"✅ Yoshi saqlandi: <b>{age}</b>\n\n"
        "<b>4-qadam:</b> Iltimos, farzandlar sonini tanlang:",
        reply_markup=get_children_count_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_guardian_children_count)


@router.callback_query(StateFilter(RegistrationStates.waiting_for_guardian_children_count), F.data.startswith("children_"))
async def process_guardian_children_count(callback: CallbackQuery, state: FSMContext):
    """Process guardian children count."""
    children_count = int(callback.data.split("_")[1])
    
    telegram_id = callback.from_user.id
    await BotStateService.update_state_data(telegram_id, guardian_children_count=children_count)
    
    children_count_label = dict(Parent.CHILDREN_COUNT_CHOICES)[children_count]
    
    await callback.message.edit_text(
        f"✅ Farzandlar soni saqlandi: <b>{children_count_label}</b>\n\n"
        "<b>5-qadam:</b> Iltimos, vasiyning kasbini kiriting:"
    )
    await callback.answer()
    await state.set_state(RegistrationStates.waiting_for_guardian_profession)


@router.message(StateFilter(RegistrationStates.waiting_for_guardian_profession))
async def process_guardian_profession(message: Message, state: FSMContext):
    """Process guardian profession."""
    profession = message.text.strip()
    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, guardian_profession=profession)
    
    await message.answer(
        f"✅ Kasbi saqlandi: <b>{profession}</b>\n\n"
        "<b>6-qadam:</b> Iltimos, vasiyning telefon raqamini kiriting (Tel1):",
        reply_markup=get_phone_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_guardian_phone1)


@router.message(StateFilter(RegistrationStates.waiting_for_guardian_phone1), F.contact)
async def process_guardian_phone1_contact(message: Message, state: FSMContext):
    """Process guardian phone from contact."""
    phone_number = message.contact.phone_number
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number
    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, guardian_phone1=phone_number)
    
    await message.answer(
        f"✅ Telefon raqami 1 saqlandi: <b>{phone_number}</b>\n\n"
        "<b>7-qadam:</b> Iltimos, vasiyning ikkinchi telefon raqamini kiriting (Tel2):\n"
        "(Agar ikkinchi raqam bo'lmasa, 'O'tkazib yuborish' tugmasini bosing)",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_guardian_phone2)


@router.message(StateFilter(RegistrationStates.waiting_for_guardian_phone1))
async def process_guardian_phone1_text(message: Message, state: FSMContext):
    """Process guardian phone from text."""
    phone_number = message.text.strip()
    
    if not phone_number.replace('+', '').replace(' ', '').replace('-', '').isdigit():
        await message.answer(
            "❌ Iltimos, to'g'ri telefon raqam kiriting yoki 'Telefon raqamini yuborish' tugmasini bosing:",
            reply_markup=get_phone_keyboard()
        )
        return
    
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number
    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, guardian_phone1=phone_number)
    
    await message.answer(
        f"✅ Telefon raqami 1 saqlandi: <b>{phone_number}</b>\n\n"
        "<b>7-qadam:</b> Iltimos, vasiyning ikkinchi telefon raqamini kiriting (Tel2):\n"
        "(Agar ikkinchi raqam bo'lmasa, 'O'tkazib yuborish' tugmasini bosing)",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_guardian_phone2)


@router.callback_query(StateFilter(RegistrationStates.waiting_for_guardian_phone2), F.data == "skip")
async def skip_guardian_phone2(callback: CallbackQuery, state: FSMContext):
    """Skip guardian phone 2."""
    telegram_id = callback.from_user.id
    await BotStateService.update_state_data(telegram_id, guardian_phone2=None)
    
    await callback.message.edit_text(
        "✅ Telefon raqami 2 o'tkazib yuborildi.\n\n"
        "<b>Qadam-3: Ustoz haqida</b>\n\n"
        "<b>1-qadam:</b> Iltimos, ustozning to'liq ismini kiriting (Ism, familiya):"
    )
    await callback.answer()
    await state.set_state(RegistrationStates.waiting_for_teacher_name)


@router.message(StateFilter(RegistrationStates.waiting_for_guardian_phone2), F.contact)
async def process_guardian_phone2_contact(message: Message, state: FSMContext):
    """Process guardian phone 2 from contact."""
    phone_number = message.contact.phone_number
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number
    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, guardian_phone2=phone_number)
    
    await message.answer(
        f"✅ Telefon raqami 2 saqlandi: <b>{phone_number}</b>\n\n"
        "<b>Qadam-3: Ustoz haqida</b>\n\n"
        "<b>1-qadam:</b> Iltimos, ustozning to'liq ismini kiriting (Ism, familiya):"
    )
    await state.set_state(RegistrationStates.waiting_for_teacher_name)


@router.message(StateFilter(RegistrationStates.waiting_for_guardian_phone2))
async def process_guardian_phone2_text(message: Message, state: FSMContext):
    """Process guardian phone 2 from text."""
    phone_number = message.text.strip()
    
    if not phone_number.replace('+', '').replace(' ', '').replace('-', '').isdigit():
        await message.answer(
            "❌ Iltimos, to'g'ri telefon raqam kiriting yoki 'O'tkazib yuborish' tugmasini bosing:",
            reply_markup=get_skip_keyboard()
        )
        return
    
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number
    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, guardian_phone2=phone_number)
    
    await message.answer(
        f"✅ Telefon raqami 2 saqlandi: <b>{phone_number}</b>\n\n"
        "<b>Qadam-3: Ustoz haqida</b>\n\n"
        "<b>1-qadam:</b> Iltimos, ustozning to'liq ismini kiriting (Ism, familiya):"
    )
    await state.set_state(RegistrationStates.waiting_for_teacher_name)


# ==================== STEP 3: TEACHER INFORMATION ====================

@router.message(StateFilter(RegistrationStates.waiting_for_teacher_name))
async def process_teacher_name(message: Message, state: FSMContext):
    """Process teacher name."""
    teacher_name = message.text.strip()
    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, teacher_name=teacher_name)
    
    await message.answer(
        f"✅ Ustoz ismi saqlandi: <b>{teacher_name}</b>\n\n"
        "<b>2-qadam:</b> Iltimos, ustozning ish joyini kiriting:"
    )
    await state.set_state(RegistrationStates.waiting_for_teacher_workplace)


@router.message(StateFilter(RegistrationStates.waiting_for_teacher_workplace))
async def process_teacher_workplace(message: Message, state: FSMContext):
    """Process teacher workplace."""
    workplace = message.text.strip()
    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, teacher_workplace=workplace)
    
    await message.answer(
        f"✅ Ish joyi saqlandi: <b>{workplace}</b>\n\n"
        "<b>3-qadam:</b> Iltimos, ustozning telefon raqamini kiriting:",
        reply_markup=get_phone_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_teacher_phone)


@router.message(StateFilter(RegistrationStates.waiting_for_teacher_phone), F.contact)
async def process_teacher_phone_contact(message: Message, state: FSMContext):
    """Process teacher phone from contact."""
    phone_number = message.contact.phone_number
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number
    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, teacher_phone=phone_number)
    
    await message.answer(
        f"✅ Ustoz telefon raqami saqlandi: <b>{phone_number}</b>\n\n"
        "<b>Qadam-4: Manba</b>\n\n"
        "<b>Qayerdan eshitdingiz?</b> Iltimos, manbani tanlang:",
        reply_markup=get_source_type_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_registration_source)


@router.message(StateFilter(RegistrationStates.waiting_for_teacher_phone))
async def process_teacher_phone_text(message: Message, state: FSMContext):
    """Process teacher phone from text."""
    phone_number = message.text.strip()
    
    if not phone_number.replace('+', '').replace(' ', '').replace('-', '').isdigit():
        await message.answer(
            "❌ Iltimos, to'g'ri telefon raqam kiriting yoki 'Telefon raqamini yuborish' tugmasini bosing:",
            reply_markup=get_phone_keyboard()
        )
        return
    
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number
    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, teacher_phone=phone_number)
    
    await message.answer(
        f"✅ Ustoz telefon raqami saqlandi: <b>{phone_number}</b>\n\n"
        "<b>Qadam-4: Manba</b>\n\n"
        "<b>Qayerdan eshitdingiz?</b> Iltimos, manbani tanlang:",
        reply_markup=get_source_type_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_registration_source)


# ==================== STEP 4: SOURCE ====================

@router.callback_query(StateFilter(RegistrationStates.waiting_for_registration_source), F.data.startswith("source_"))
async def process_registration_source(callback: CallbackQuery, state: FSMContext):
    """Process registration source."""
    source_type = callback.data.split("_", 1)[1]
    
    telegram_id = callback.from_user.id
    await BotStateService.update_state_data(telegram_id, source_type=source_type)
    
    if source_type == "boshqa":
        source_label = dict(RegistrationSource.SOURCE_TYPE_CHOICES)[source_type]
        await callback.message.edit_text(
            f"✅ Manba turi: <b>{source_label}</b>\n\n"
            "<b>Iltimos, batafsil ma'lumot kiriting:</b>"
        )
        await callback.answer()
        await state.set_state(RegistrationStates.waiting_for_source_details)
    else:
        # Save all data and show confirmation
        await save_all_data_and_show_confirmation(callback, state, telegram_id, source_type, None)


@router.message(StateFilter(RegistrationStates.waiting_for_source_details))
async def process_source_details(message: Message, state: FSMContext):
    """Process source details."""
    source_details = message.text.strip()
    
    telegram_id = message.from_user.id
    await BotStateService.update_state_data(telegram_id, source_details=source_details)
    
    # Save all data and show confirmation
    await save_all_data_and_show_confirmation(message, state, telegram_id, "boshqa", source_details)


# ==================== CONFIRMATION ====================

async def save_all_data_and_show_confirmation(message_or_callback, state: FSMContext, telegram_id: int, source_type: str, source_details: str = None):
    """Save all collected data and show confirmation page."""
    # Get all state data
    state_data = await BotStateService.get_state(telegram_id)
    data = state_data.state_data if state_data else {}
    
    # Get student
    student = await StudentService.get_student(telegram_id)
    
    # Save guardian (parent)
    guardian_name = data.get('guardian_name')
    guardian_relationship = data.get('guardian_relationship')
    guardian_age = data.get('guardian_age')
    guardian_children_count = data.get('guardian_children_count')
    guardian_profession = data.get('guardian_profession')
    guardian_phone1 = data.get('guardian_phone1')
    guardian_phone2 = data.get('guardian_phone2')
    
    if guardian_name:
        await StudentService.create_parent(
            student,
            full_name=guardian_name,
            phone_number=guardian_phone1,
            phone_number2=guardian_phone2,
            relationship=guardian_relationship,
            age=guardian_age,
            children_count=guardian_children_count,
            profession=guardian_profession
        )
    
    # Save teacher
    teacher_name = data.get('teacher_name')
    teacher_workplace = data.get('teacher_workplace')
    teacher_phone = data.get('teacher_phone')
    
    if teacher_name:
        await StudentService.create_teacher(
            student,
            full_name=teacher_name,
            phone_number=teacher_phone,
            workplace=teacher_workplace
        )
    
    # Save registration source
    await StudentService.create_registration_source(
        student,
        source_type=source_type,
        source_details=source_details
    )
    
    # Build confirmation message
    confirmation_text = "<b>📋 Tasdiqlash</b>\n\n"
    confirmation_text += "<b>O'quvchi:</b>\n"
    confirmation_text += f"• Ism: {student.first_name}\n"
    confirmation_text += f"• Familiya: {student.last_name or 'Kiritilmadi'}\n"
    confirmation_text += f"• Sharif: {student.middle_name or 'Kiritilmadi'}\n"
    confirmation_text += f"• Tug'ilgan sana: {student.date_of_birth or 'Kiritilmadi'}\n"
    confirmation_text += f"• Metrika raqami: {student.document_number or 'Kiritilmadi'}\n"
    confirmation_text += f"• Viloyat: {dict(Student.REGION_CHOICES).get(student.region, 'Kiritilmadi')}\n"
    confirmation_text += f"• Tuman/shahar: {student.district or 'Kiritilmadi'}\n"
    confirmation_text += f"• Maktab: {student.school_name or 'Kiritilmadi'}\n"
    confirmation_text += f"• Sinf: {dict(Student.GRADE_CHOICES).get(student.grade, 'Kiritilmadi')}\n"
    confirmation_text += f"• O'qish tili: {dict(Student.LANGUAGE_CHOICES).get(student.language, 'Kiritilmadi')}\n"
    confirmation_text += f"• Foto: {'Yuborilgan' if student.photo else 'Kiritilmadi'}\n"
    confirmation_text += f"• Avvalgi yutuqlar izohi: {student.achievements_description or 'Kiritilmadi'}\n"
    confirmation_text += f"• Avvalgi yutuqlar fayli: {'Yuborilgan' if student.achievements_file else 'Kiritilmadi'}\n\n"
    
    confirmation_text += "<b>Vasiy:</b>\n"
    if guardian_name:
        confirmation_text += f"• Ism, familiya: {guardian_name}\n"
        confirmation_text += f"• Kimligi: {dict(Parent.RELATIONSHIP_CHOICES).get(guardian_relationship, 'Kiritilmadi')}\n"
        confirmation_text += f"• Yoshi: {guardian_age or 'Kiritilmadi'}\n"
        confirmation_text += f"• Farzandlar soni: {dict(Parent.CHILDREN_COUNT_CHOICES).get(guardian_children_count, 'Kiritilmadi')}\n"
        confirmation_text += f"• Kasbi: {guardian_profession or 'Kiritilmadi'}\n"
        confirmation_text += f"• Tel1: {guardian_phone1 or 'Kiritilmadi'}\n"
        confirmation_text += f"• Tel2: {guardian_phone2 or 'Kiritilmadi'}\n\n"
    else:
        confirmation_text += "Ma'lumotlar kiritilmadi\n\n"
    
    confirmation_text += "<b>Ustoz:</b>\n"
    if teacher_name:
        confirmation_text += f"• Ism, familiya: {teacher_name}\n"
        confirmation_text += f"• Ish joyi: {teacher_workplace or 'Kiritilmadi'}\n"
        confirmation_text += f"• Telefon: {teacher_phone or 'Kiritilmadi'}\n\n"
    else:
        confirmation_text += "Ma'lumotlar kiritilmadi\n\n"
    
    confirmation_text += "<b>Manba:</b>\n"
    source_label = dict(RegistrationSource.SOURCE_TYPE_CHOICES).get(source_type, 'Kiritilmadi')
    confirmation_text += f"• {source_label}\n"
    if source_details:
        confirmation_text += f"• Tafsilotlar: {source_details}\n"
    
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
    
    await callback.message.edit_text(
        "🎉 <b>Tabriklaymiz!</b> Ro'yxatdan o'tish muvaffaqiyatli yakunlandi!\n\n"
        "Endi siz imtihonlarni topshirishingiz mumkin."
    )
    await callback.answer()
    
    # Clear state
    await state.clear()
    await BotStateService.clear_state(telegram_id)
    
    await callback.message.answer(
        "Quyidagi menyudan kerakli bo'limni tanlang:",
        reply_markup=get_main_menu_keyboard()
    )


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
        'middle_name': "Iltimos, yangi sharif kiriting (yoki 'O'tkazib yuborish'):",
        'date_of_birth': "Iltimos, yangi tug'ilgan sana kiriting (YYYY-MM-DD):",
        'document_number': "Iltimos, yangi metrika raqami kiriting:",
        'region': "Iltimos, yangi viloyat tanlang:",
        'district': "Iltimos, yangi tuman/shahar kiriting:",
        'school_name': "Iltimos, yangi maktab nomi kiriting:",
        'grade': "Iltimos, yangi sinf tanlang:",
        'language': "Iltimos, yangi o'qish tili tanlang:",
        'photo': "Iltimos, yangi rasm yuboring:",
        'achievements_description': "Iltimos, yangi avvalgi yutuqlar izohi kiriting (yoki 'O'tkazib yuborish'):",
        'achievements_file': "Iltimos, yangi avvalgi yutuqlar faylini/rasmini yuboring (yoki 'O'tkazib yuborish'):",
        'guardian_name': "Iltimos, yangi vasiy ismi kiriting:",
        'guardian_relationship': "Iltimos, yangi vasiy kimligi tanlang:",
        'guardian_age': "Iltimos, yangi vasiy yoshi kiriting:",
        'guardian_children_count': "Iltimos, yangi farzandlar soni tanlang:",
        'guardian_profession': "Iltimos, yangi vasiy kasbi kiriting:",
        'guardian_phone1': "Iltimos, yangi vasiy tel1 kiriting:",
        'guardian_phone2': "Iltimos, yangi vasiy tel2 kiriting (yoki 'O'tkazib yuborish'):",
        'teacher_name': "Iltimos, yangi ustoz ismi kiriting:",
        'teacher_workplace': "Iltimos, yangi ustoz ish joyi kiriting:",
        'teacher_phone': "Iltimos, yangi ustoz telefon raqami kiriting:",
        'source': "Iltimos, yangi manba tanlang:",
    }
    
    prompt = field_prompts.get(field_name, "Iltimos, yangi ma'lumot kiriting:")
    
    # Handle special cases that need keyboards
    if field_name == 'region':
        await callback.message.edit_text(prompt, reply_markup=get_region_keyboard())
    elif field_name == 'grade':
        await callback.message.edit_text(prompt, reply_markup=get_grade_keyboard())
    elif field_name == 'language':
        await callback.message.edit_text(prompt, reply_markup=get_language_keyboard())
    elif field_name == 'guardian_relationship':
        await callback.message.edit_text(prompt, reply_markup=get_relationship_keyboard())
    elif field_name == 'guardian_children_count':
        await callback.message.edit_text(prompt, reply_markup=get_children_count_keyboard())
    elif field_name == 'source':
        await callback.message.edit_text(prompt, reply_markup=get_source_type_keyboard())
    elif field_name in ['middle_name', 'achievements_description', 'achievements_file', 'guardian_phone2']:
        await callback.message.edit_text(prompt, reply_markup=get_skip_keyboard())
    elif field_name in ['guardian_phone1', 'teacher_phone']:
        await callback.message.edit_text(prompt, reply_markup=get_phone_keyboard())
    else:
        await callback.message.edit_text(prompt)
    
    await callback.answer()
    await state.set_state(RegistrationStates.editing_field)


@router.callback_query(StateFilter(RegistrationStates.waiting_for_edit_field), F.data == "back_to_confirmation")
async def back_to_confirmation(callback: CallbackQuery, state: FSMContext):
    """Go back to confirmation."""
    telegram_id = callback.from_user.id
    student = await StudentService.get_student(telegram_id)
    
    # Get parent and teacher
    @sync_to_async
    def get_related_objects():
        try:
            parent = student.parent
        except Parent.DoesNotExist:
            parent = None
        try:
            teacher = student.teacher
        except Teacher.DoesNotExist:
            teacher = None
        try:
            source = student.registration_source
        except RegistrationSource.DoesNotExist:
            source = None
        return parent, teacher, source
    
    parent, teacher, source = await get_related_objects()
    
    # Rebuild confirmation message
    confirmation_text = "<b>📋 Tasdiqlash</b>\n\n"
    confirmation_text += "<b>O'quvchi:</b>\n"
    confirmation_text += f"• Ism: {student.first_name}\n"
    confirmation_text += f"• Familiya: {student.last_name or 'Kiritilmadi'}\n"
    confirmation_text += f"• Sharif: {student.middle_name or 'Kiritilmadi'}\n"
    confirmation_text += f"• Tug'ilgan sana: {student.date_of_birth or 'Kiritilmadi'}\n"
    confirmation_text += f"• Metrika raqami: {student.document_number or 'Kiritilmadi'}\n"
    confirmation_text += f"• Viloyat: {dict(Student.REGION_CHOICES).get(student.region, 'Kiritilmadi')}\n"
    confirmation_text += f"• Tuman/shahar: {student.district or 'Kiritilmadi'}\n"
    confirmation_text += f"• Maktab: {student.school_name or 'Kiritilmadi'}\n"
    confirmation_text += f"• Sinf: {dict(Student.GRADE_CHOICES).get(student.grade, 'Kiritilmadi')}\n"
    confirmation_text += f"• O'qish tili: {dict(Student.LANGUAGE_CHOICES).get(student.language, 'Kiritilmadi')}\n"
    confirmation_text += f"• Foto: {'Yuborilgan' if student.photo else 'Kiritilmadi'}\n"
    confirmation_text += f"• Avvalgi yutuqlar izohi: {student.achievements_description or 'Kiritilmadi'}\n"
    confirmation_text += f"• Avvalgi yutuqlar fayli: {'Yuborilgan' if student.achievements_file else 'Kiritilmadi'}\n\n"
    
    confirmation_text += "<b>Vasiy:</b>\n"
    if parent:
        confirmation_text += f"• Ism, familiya: {parent.full_name}\n"
        confirmation_text += f"• Kimligi: {dict(Parent.RELATIONSHIP_CHOICES).get(parent.relationship, 'Kiritilmadi')}\n"
        confirmation_text += f"• Yoshi: {parent.age or 'Kiritilmadi'}\n"
        confirmation_text += f"• Farzandlar soni: {dict(Parent.CHILDREN_COUNT_CHOICES).get(parent.children_count, 'Kiritilmadi')}\n"
        confirmation_text += f"• Kasbi: {parent.profession or 'Kiritilmadi'}\n"
        confirmation_text += f"• Tel1: {parent.phone_number or 'Kiritilmadi'}\n"
        confirmation_text += f"• Tel2: {parent.phone_number2 or 'Kiritilmadi'}\n\n"
    else:
        confirmation_text += "Ma'lumotlar kiritilmadi\n\n"
    
    confirmation_text += "<b>Ustoz:</b>\n"
    if teacher:
        confirmation_text += f"• Ism, familiya: {teacher.full_name}\n"
        confirmation_text += f"• Ish joyi: {teacher.workplace or 'Kiritilmadi'}\n"
        confirmation_text += f"• Telefon: {teacher.phone_number or 'Kiritilmadi'}\n\n"
    else:
        confirmation_text += "Ma'lumotlar kiritilmadi\n\n"
    
    confirmation_text += "<b>Manba:</b>\n"
    if source:
        source_label = dict(RegistrationSource.SOURCE_TYPE_CHOICES).get(source.source_type, 'Kiritilmadi')
        confirmation_text += f"• {source_label}\n"
        if source.source_details:
            confirmation_text += f"• Tafsilotlar: {source.source_details}\n"
    else:
        confirmation_text += "Ma'lumotlar kiritilmadi\n"
    
    await callback.message.edit_text(confirmation_text, reply_markup=get_confirmation_keyboard())
    await callback.answer()
    await state.set_state(RegistrationStates.waiting_for_confirmation)


# Handle editing different field types
# This is a simplified version - you'll need to handle each field type appropriately
# For brevity, I'll show a few examples and you can extend

from asgiref.sync import sync_to_async

@router.message(StateFilter(RegistrationStates.editing_field))
async def process_field_edit(message: Message, state: FSMContext):
    """Process field edit for student fields only."""
    telegram_id = message.from_user.id
    state_data = await BotStateService.get_state(telegram_id)
    editing_field = state_data.state_data.get('editing_field') if state_data else None
    editing_source_type = state_data.state_data.get('editing_source_type') if state_data else None
    
    # Skip if handling source details or guardian/teacher fields (handled by other handlers)
    if editing_source_type or (editing_field and editing_field.startswith(('guardian_', 'teacher_'))):
        return
    
    if not editing_field:
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")
        return
    
    student = await StudentService.get_student(telegram_id)
    
    # Handle text fields
    if editing_field in ['first_name', 'last_name', 'middle_name', 'document_number', 'district', 'school_name', 'achievements_description']:
        value = message.text.strip() if message.text else None
        if editing_field == 'middle_name' and not value:
            value = None
        await StudentService.update_student(telegram_id, **{editing_field: value})
        await message.answer(f"✅ {editing_field} yangilandi!")
    
    # Handle date
    elif editing_field == 'date_of_birth':
        try:
            date_of_birth = datetime.strptime(message.text.strip(), "%Y-%m-%d").date()
            await StudentService.update_student(telegram_id, date_of_birth=date_of_birth)
            await message.answer("✅ Tug'ilgan sana yangilandi!")
        except ValueError:
            await message.answer("❌ Iltimos, to'g'ri formatda kiriting (YYYY-MM-DD):")
            return
    else:
        # Not a student field, skip
        return
    
    # After editing, return to confirmation
    await show_confirmation_after_edit(message, state, telegram_id)


@router.callback_query(StateFilter(RegistrationStates.editing_field), F.data.startswith("region_"))
async def edit_region(callback: CallbackQuery, state: FSMContext):
    """Edit region."""
    region = callback.data.split("_", 1)[1]
    telegram_id = callback.from_user.id
    await StudentService.update_student(telegram_id, region=region)
    await callback.answer("✅ Viloyat yangilandi!")
    await show_confirmation_after_edit(callback.message, state, telegram_id)


@router.callback_query(StateFilter(RegistrationStates.editing_field), F.data.startswith("grade_"))
async def edit_grade(callback: CallbackQuery, state: FSMContext):
    """Edit grade."""
    grade = int(callback.data.split("_")[1])
    telegram_id = callback.from_user.id
    await StudentService.update_student(telegram_id, grade=grade)
    await callback.answer("✅ Sinf yangilandi!")
    await show_confirmation_after_edit(callback.message, state, telegram_id)


@router.callback_query(StateFilter(RegistrationStates.editing_field), F.data.startswith("language_"))
async def edit_language(callback: CallbackQuery, state: FSMContext):
    """Edit language."""
    language = callback.data.split("_")[1]
    telegram_id = callback.from_user.id
    await StudentService.update_student(telegram_id, language=language)
    await callback.answer("✅ O'qish tili yangilandi!")
    await show_confirmation_after_edit(callback.message, state, telegram_id)


@router.message(StateFilter(RegistrationStates.editing_field), F.photo)
async def edit_photo(message: Message, state: FSMContext):
    """Edit photo."""
    telegram_id = message.from_user.id
    state_data = await BotStateService.get_state(telegram_id)
    editing_field = state_data.state_data.get('editing_field') if state_data else None
    
    photo = message.photo[-1]
    
    from django.conf import settings
    from exam_bot_admin.webhook import bot
    import os
    
    file = await bot.get_file(photo.file_id)
    
    if editing_field == 'photo':
        media_dir = os.path.join(settings.MEDIA_ROOT, 'students')
        os.makedirs(media_dir, exist_ok=True)
        file_path = os.path.join(media_dir, f"{telegram_id}_{photo.file_id}.jpg")
        await bot.download_file(file.file_path, file_path)
        relative_path = f"students/{telegram_id}_{photo.file_id}.jpg"
        await StudentService.update_student(telegram_id, photo=relative_path)
        await message.answer("✅ Foto yangilandi!")
    elif editing_field == 'achievements_file':
        media_dir = os.path.join(settings.MEDIA_ROOT, 'students', 'achievements')
        os.makedirs(media_dir, exist_ok=True)
        file_path = os.path.join(media_dir, f"{telegram_id}_{photo.file_id}.jpg")
        await bot.download_file(file.file_path, file_path)
        relative_path = f"students/achievements/{telegram_id}_{photo.file_id}.jpg"
        await StudentService.update_student(telegram_id, achievements_file=relative_path)
        await message.answer("✅ Avvalgi yutuqlar fayli yangilandi!")
    
    await show_confirmation_after_edit(message, state, telegram_id)


@router.message(StateFilter(RegistrationStates.editing_field), F.document)
async def edit_achievements_file_document(message: Message, state: FSMContext):
    """Edit achievements file (document)."""
    telegram_id = message.from_user.id
    state_data = await BotStateService.get_state(telegram_id)
    editing_field = state_data.state_data.get('editing_field') if state_data else None
    
    if editing_field != 'achievements_file':
        return
    
    from django.conf import settings
    from exam_bot_admin.webhook import bot
    import os
    
    file = await bot.get_file(message.document.file_id)
    media_dir = os.path.join(settings.MEDIA_ROOT, 'students', 'achievements')
    os.makedirs(media_dir, exist_ok=True)
    file_path = os.path.join(media_dir, f"{telegram_id}_{message.document.file_id}_{message.document.file_name}")
    await bot.download_file(file.file_path, file_path)
    relative_path = f"students/achievements/{telegram_id}_{message.document.file_id}_{message.document.file_name}"
    
    await StudentService.update_student(telegram_id, achievements_file=relative_path)
    await message.answer("✅ Avvalgi yutuqlar fayli yangilandi!")
    await show_confirmation_after_edit(message, state, telegram_id)


@router.callback_query(StateFilter(RegistrationStates.editing_field), F.data == "skip")
async def skip_field_edit(callback: CallbackQuery, state: FSMContext):
    """Skip field edit (for optional fields)."""
    telegram_id = callback.from_user.id
    state_data = await BotStateService.get_state(telegram_id)
    editing_field = state_data.state_data.get('editing_field') if state_data else None
    
    if editing_field in ['middle_name', 'achievements_description', 'achievements_file', 'guardian_phone2']:
        if editing_field == 'middle_name':
            await StudentService.update_student(telegram_id, middle_name=None)
            await callback.answer("✅ Sharif o'chirildi!")
        elif editing_field == 'achievements_description':
            await StudentService.update_student(telegram_id, achievements_description=None)
            await callback.answer("✅ Avvalgi yutuqlar izohi o'chirildi!")
        elif editing_field == 'achievements_file':
            await StudentService.update_student(telegram_id, achievements_file=None)
            await callback.answer("✅ Avvalgi yutuqlar fayli o'chirildi!")
        elif editing_field == 'guardian_phone2':
            student = await StudentService.get_student(telegram_id)
            await StudentService.update_parent(student, phone_number2=None)
            await callback.answer("✅ Vasiy tel2 o'chirildi!")
        
        await show_confirmation_after_edit(callback.message, state, telegram_id)


@router.callback_query(StateFilter(RegistrationStates.editing_field), F.data.startswith("relationship_"))
async def edit_guardian_relationship(callback: CallbackQuery, state: FSMContext):
    """Edit guardian relationship."""
    relationship = callback.data.split("_", 1)[1]
    telegram_id = callback.from_user.id
    student = await StudentService.get_student(telegram_id)
    await StudentService.update_parent(student, relationship=relationship)
    await callback.answer("✅ Vasiy kimligi yangilandi!")
    await show_confirmation_after_edit(callback.message, state, telegram_id)


@router.callback_query(StateFilter(RegistrationStates.editing_field), F.data.startswith("children_"))
async def edit_guardian_children_count(callback: CallbackQuery, state: FSMContext):
    """Edit guardian children count."""
    children_count = int(callback.data.split("_")[1])
    telegram_id = callback.from_user.id
    student = await StudentService.get_student(telegram_id)
    await StudentService.update_parent(student, children_count=children_count)
    await callback.answer("✅ Farzandlar soni yangilandi!")
    await show_confirmation_after_edit(callback.message, state, telegram_id)


@router.callback_query(StateFilter(RegistrationStates.editing_field), F.data.startswith("source_"))
async def edit_source(callback: CallbackQuery, state: FSMContext):
    """Edit registration source."""
    source_type = callback.data.split("_", 1)[1]
    telegram_id = callback.from_user.id
    student = await StudentService.get_student(telegram_id)
    
    if source_type == "boshqa":
        await callback.message.edit_text("Iltimos, batafsil ma'lumot kiriting:")
        await BotStateService.update_state_data(telegram_id, editing_source_type=source_type)
        await callback.answer()
        return
    
    await StudentService.update_registration_source(student, source_type=source_type, source_details=None)
    await callback.answer("✅ Manba yangilandi!")
    await show_confirmation_after_edit(callback.message, state, telegram_id)


@router.message(StateFilter(RegistrationStates.editing_field))
async def process_field_edit_extended(message: Message, state: FSMContext):
    """Process field edit for guardian and teacher fields."""
    telegram_id = message.from_user.id
    state_data = await BotStateService.get_state(telegram_id)
    editing_field = state_data.state_data.get('editing_field') if state_data else None
    editing_source_type = state_data.state_data.get('editing_source_type') if state_data else None
    
    if not editing_field and not editing_source_type:
        # This will be handled by the other process_field_edit handler
        return
    
    student = await StudentService.get_student(telegram_id)
    
    # Handle source details
    if editing_source_type:
        source_details = message.text.strip()
        await StudentService.update_registration_source(student, source_type=editing_source_type, source_details=source_details)
        await message.answer("✅ Manba yangilandi!")
        await BotStateService.update_state_data(telegram_id, editing_source_type=None)
        await show_confirmation_after_edit(message, state, telegram_id)
        return
    
    # Handle guardian fields
    if editing_field == 'guardian_name':
        value = message.text.strip()
        await StudentService.update_parent(student, full_name=value)
        await message.answer("✅ Vasiy ismi yangilandi!")
    elif editing_field == 'guardian_age':
        try:
            age = int(message.text.strip())
            if age < 1 or age > 150:
                raise ValueError
            await StudentService.update_parent(student, age=age)
            await message.answer("✅ Vasiy yoshi yangilandi!")
        except ValueError:
            await message.answer("❌ Iltimos, to'g'ri yosh kiriting (1-150):")
            return
    elif editing_field == 'guardian_profession':
        value = message.text.strip()
        await StudentService.update_parent(student, profession=value)
        await message.answer("✅ Vasiy kasbi yangilandi!")
    elif editing_field == 'guardian_phone1':
        phone_number = message.text.strip()
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
        await StudentService.update_parent(student, phone_number=phone_number)
        await message.answer("✅ Vasiy tel1 yangilandi!")
    elif editing_field == 'guardian_phone2':
        phone_number = message.text.strip()
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
        await StudentService.update_parent(student, phone_number2=phone_number)
        await message.answer("✅ Vasiy tel2 yangilandi!")
    # Handle teacher fields
    elif editing_field == 'teacher_name':
        value = message.text.strip()
        await StudentService.update_teacher(student, full_name=value)
        await message.answer("✅ Ustoz ismi yangilandi!")
    elif editing_field == 'teacher_workplace':
        value = message.text.strip()
        await StudentService.update_teacher(student, workplace=value)
        await message.answer("✅ Ustoz ish joyi yangilandi!")
    elif editing_field == 'teacher_phone':
        phone_number = message.text.strip()
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
        await StudentService.update_teacher(student, phone_number=phone_number)
        await message.answer("✅ Ustoz telefon raqami yangilandi!")
    else:
        # This should be handled by the other handler
        return
    
    await show_confirmation_after_edit(message, state, telegram_id)


@router.message(StateFilter(RegistrationStates.editing_field), F.contact)
async def edit_phone_from_contact(message: Message, state: FSMContext):
    """Edit phone from contact."""
    telegram_id = message.from_user.id
    state_data = await BotStateService.get_state(telegram_id)
    editing_field = state_data.state_data.get('editing_field') if state_data else None
    
    phone_number = message.contact.phone_number
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number
    
    student = await StudentService.get_student(telegram_id)
    
    if editing_field == 'guardian_phone1':
        await StudentService.update_parent(student, phone_number=phone_number)
        await message.answer("✅ Vasiy tel1 yangilandi!")
    elif editing_field == 'guardian_phone2':
        await StudentService.update_parent(student, phone_number2=phone_number)
        await message.answer("✅ Vasiy tel2 yangilandi!")
    elif editing_field == 'teacher_phone':
        await StudentService.update_teacher(student, phone_number=phone_number)
        await message.answer("✅ Ustoz telefon raqami yangilandi!")
    else:
        return
    
    await show_confirmation_after_edit(message, state, telegram_id)

async def show_confirmation_after_edit(message_or_callback, state: FSMContext, telegram_id: int):
    """Show confirmation page after editing a field."""
    student = await StudentService.get_student(telegram_id)
    
    # Get related objects
    @sync_to_async
    def get_related_objects():
        try:
            parent = student.parent
        except Parent.DoesNotExist:
            parent = None
        try:
            teacher = student.teacher
        except Teacher.DoesNotExist:
            teacher = None
        try:
            source = student.registration_source
        except RegistrationSource.DoesNotExist:
            source = None
        return parent, teacher, source
    
    parent, teacher, source = await get_related_objects()
    
    # Build confirmation message (same as before)
    confirmation_text = "<b>📋 Tasdiqlash</b>\n\n"
    confirmation_text += "<b>O'quvchi:</b>\n"
    confirmation_text += f"• Ism: {student.first_name}\n"
    confirmation_text += f"• Familiya: {student.last_name or 'Kiritilmadi'}\n"
    confirmation_text += f"• Sharif: {student.middle_name or 'Kiritilmadi'}\n"
    confirmation_text += f"• Tug'ilgan sana: {student.date_of_birth or 'Kiritilmadi'}\n"
    confirmation_text += f"• Metrika raqami: {student.document_number or 'Kiritilmadi'}\n"
    confirmation_text += f"• Viloyat: {dict(Student.REGION_CHOICES).get(student.region, 'Kiritilmadi')}\n"
    confirmation_text += f"• Tuman/shahar: {student.district or 'Kiritilmadi'}\n"
    confirmation_text += f"• Maktab: {student.school_name or 'Kiritilmadi'}\n"
    confirmation_text += f"• Sinf: {dict(Student.GRADE_CHOICES).get(student.grade, 'Kiritilmadi')}\n"
    confirmation_text += f"• O'qish tili: {dict(Student.LANGUAGE_CHOICES).get(student.language, 'Kiritilmadi')}\n"
    confirmation_text += f"• Foto: {'Yuborilgan' if student.photo else 'Kiritilmadi'}\n"
    confirmation_text += f"• Avvalgi yutuqlar izohi: {student.achievements_description or 'Kiritilmadi'}\n"
    confirmation_text += f"• Avvalgi yutuqlar fayli: {'Yuborilgan' if student.achievements_file else 'Kiritilmadi'}\n\n"
    
    confirmation_text += "<b>Vasiy:</b>\n"
    if parent:
        confirmation_text += f"• Ism, familiya: {parent.full_name}\n"
        confirmation_text += f"• Kimligi: {dict(Parent.RELATIONSHIP_CHOICES).get(parent.relationship, 'Kiritilmadi')}\n"
        confirmation_text += f"• Yoshi: {parent.age or 'Kiritilmadi'}\n"
        confirmation_text += f"• Farzandlar soni: {dict(Parent.CHILDREN_COUNT_CHOICES).get(parent.children_count, 'Kiritilmadi')}\n"
        confirmation_text += f"• Kasbi: {parent.profession or 'Kiritilmadi'}\n"
        confirmation_text += f"• Tel1: {parent.phone_number or 'Kiritilmadi'}\n"
        confirmation_text += f"• Tel2: {parent.phone_number2 or 'Kiritilmadi'}\n\n"
    else:
        confirmation_text += "Ma'lumotlar kiritilmadi\n\n"
    
    confirmation_text += "<b>Ustoz:</b>\n"
    if teacher:
        confirmation_text += f"• Ism, familiya: {teacher.full_name}\n"
        confirmation_text += f"• Ish joyi: {teacher.workplace or 'Kiritilmadi'}\n"
        confirmation_text += f"• Telefon: {teacher.phone_number or 'Kiritilmadi'}\n\n"
    else:
        confirmation_text += "Ma'lumotlar kiritilmadi\n\n"
    
    confirmation_text += "<b>Manba:</b>\n"
    if source:
        source_label = dict(RegistrationSource.SOURCE_TYPE_CHOICES).get(source.source_type, 'Kiritilmadi')
        confirmation_text += f"• {source_label}\n"
        if source.source_details:
            confirmation_text += f"• Tafsilotlar: {source.source_details}\n"
    else:
        confirmation_text += "Ma'lumotlar kiritilmadi\n"
    
    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(confirmation_text, reply_markup=get_confirmation_keyboard())
        await message_or_callback.answer()
    else:
        await message_or_callback.answer(confirmation_text, reply_markup=get_confirmation_keyboard())
    
    await state.set_state(RegistrationStates.waiting_for_confirmation)
