"""Admin command handlers."""
import logging
import os
from pathlib import Path
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from django.conf import settings
from asgiref.sync import sync_to_async

from bot.states import AdminStates
from bot.constants import (
    ADMIN_BROADCAST_START, ADMIN_BROADCAST_MEDIA, ADMIN_BROADCAST_TARGET,
    ADMIN_BROADCAST_CONFIRM, ADMIN_BROADCAST_SENDING, ADMIN_BROADCAST_SUCCESS,
    ADMIN_NOT_AUTHORIZED, ADMIN_BROADCAST_CANCELLED, ADMIN_MEDIA_ADDED, ADMIN_NO_TARGETS,
)
from admin_panel.models import BroadcastMessage, BroadcastMedia, Student
from bot.services import BroadcastService

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    """Check if user is an admin."""
    return user_id in settings.ADMIN_IDS


def get_target_keyboard(selected_targets: dict) -> InlineKeyboardMarkup:
    """Create inline keyboard for target selection."""
    keyboard = []
    
    # All users option
    all_users = selected_targets.get('all_users', False)
    all_text = "✅ Barcha foydalanuvchilar" if all_users else "⬜ Barcha foydalanuvchilar"
    keyboard.append([InlineKeyboardButton(text=all_text, callback_data="target_all")])
    
    # Grade options (2x2 layout)
    grade_row_1 = []
    grade_row_2 = []
    for grade in [5, 6, 7, 8]:
        is_selected = selected_targets.get(f'grade_{grade}', False)
        text = f"✅ {grade}-sinf" if is_selected else f"⬜ {grade}-sinf"
        btn = InlineKeyboardButton(text=text, callback_data=f"target_grade_{grade}")
        if grade in [5, 6]:
            grade_row_1.append(btn)
        else:
            grade_row_2.append(btn)
    
    keyboard.append(grade_row_1)
    keyboard.append(grade_row_2)
    
    # Not fully registered option
    not_reg = selected_targets.get('not_fully_registered', False)
    not_reg_text = "✅ Faqat to'liq ro'yxatdan o'tmaganlarga" if not_reg else "⬜ To'liq ro'yxatdan o'tmaganlarga"
    keyboard.append([InlineKeyboardButton(text=not_reg_text, callback_data="target_not_reg")])
    
    # Registration button option
    include_reg_btn = selected_targets.get('include_reg_btn', False)
    include_reg_btn_text = "✅ Ro'yxatdan o'tish tugmasini qo'shish" if include_reg_btn else "⬜ Ro'yxatdan o'tish tugmasini qo'shish"
    keyboard.append([InlineKeyboardButton(text=include_reg_btn_text, callback_data="target_include_reg_btn")])
    
    # Action buttons
    keyboard.append([
        InlineKeyboardButton(text="✅ Davom etish", callback_data="target_done"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="target_cancel")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Create confirmation keyboard."""
    keyboard = [
        [
            InlineKeyboardButton(text="✅ Yuborish", callback_data="confirm_send"),
            InlineKeyboardButton(text="🔙 Orqaga", callback_data="confirm_back"),
        ],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="confirm_cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_certificate_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Create certificate send confirmation keyboard."""
    keyboard = [
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="certbulk_send"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="certbulk_cancel"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


CERTIFICATE_TEST_IDS = [21, 25, 22, 26, 23, 27, 24, 28]


@sync_to_async
def collect_certificate_recipients(test_ids: list[int]) -> tuple[list[dict], str | None]:
    """Return one latest submitted attempt per student for the requested tests."""
    from admin_panel.models import Test, TestAttempt

    tests = list(Test.objects.filter(id__in=test_ids).order_by('id'))
    found_test_ids = {test.id for test in tests}
    missing_ids = [tid for tid in test_ids if tid not in found_test_ids]
    if missing_ids:
        return [], f"Quyidagi test ID lar topilmadi: {', '.join(map(str, missing_ids))}."

    attempts = list(
        TestAttempt.objects.filter(
            test_id__in=test_ids,
            status='SUBMITTED_FINAL',
            student__is_active=True,
        )
        .select_related('student', 'test')
        .order_by('student_id', '-submitted_at', '-created_at', '-id')
    )

    recipients = []
    seen_student_ids = set()

    for attempt in attempts:
        if attempt.student_id in seen_student_ids:
            continue
        seen_student_ids.add(attempt.student_id)
        recipients.append(
            {
                'attempt_id': attempt.id,
                'student_id': attempt.student_id,
                'telegram_id': attempt.student.telegram_id,
                'student_name': f"{attempt.student.first_name} {attempt.student.last_name or ''}".strip(),
                'test_id': attempt.test_id,
                'test_title': attempt.test.title,
            }
        )

    return recipients, None


@sync_to_async
def generate_certificate_preview(attempt_id: int) -> tuple[str, str, str]:
    """Generate a preview certificate for the given attempt."""
    from admin_panel.models import TestAttempt
    from admin_panel.certificate_generator import generate_certificate

    attempt = TestAttempt.objects.select_related('student', 'test').get(id=attempt_id)
    certificate_path, _certificate_number = generate_certificate(attempt.student, attempt)
    student_name = f"{attempt.student.first_name} {attempt.student.last_name or ''}".strip()
    return certificate_path, student_name, attempt.test.title


@sync_to_async
def send_certificates_to_attempts(attempt_ids: list[int]) -> tuple[int, int]:
    """Generate and send certificates for provided attempts."""
    import time
    from admin_panel.models import TestAttempt
    from admin_panel.certificate_generator import generate_certificate
    from admin_panel.utils import send_certificate_message

    sent_count = 0
    error_count = 0

    attempts = list(
        TestAttempt.objects.filter(id__in=attempt_ids)
        .select_related('student', 'test')
        .order_by('id')
    )
    attempt_by_id = {attempt.id: attempt for attempt in attempts}

    for attempt_id in attempt_ids:
        attempt = attempt_by_id.get(attempt_id)
        if not attempt:
            error_count += 1
            logger.error("Certificate send skipped because attempt %s was not found", attempt_id)
            continue

        try:
            certificate_path, _certificate_number = generate_certificate(attempt.student, attempt)
            send_certificate_message(
                attempt.student.telegram_id,
                certificate_path,
                delay_seconds=0.0,
            )
            sent_count += 1
            time.sleep(1.0)
        except Exception as e:
            error_count += 1
            logger.error(
                "Failed to send certificate to student %s (attempt %s): %s",
                attempt.student.telegram_id,
                attempt.id,
                e,
                exc_info=True,
            )

    return sent_count, error_count


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    """Start broadcast message flow (admin only)."""
    if not is_admin(message.from_user.id):
        await message.answer(ADMIN_NOT_AUTHORIZED)
        return
    
    await state.set_state(AdminStates.waiting_for_broadcast_text)
    await state.update_data(media_files=[], selected_targets={})
    await message.answer(ADMIN_BROADCAST_START, parse_mode=ParseMode.HTML)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Cancel broadcast flow."""
    current_state = await state.get_state()
    if current_state and current_state.startswith("AdminStates:"):
        await state.clear()
        await message.answer(ADMIN_BROADCAST_CANCELLED)


@router.message(StateFilter(AdminStates.waiting_for_broadcast_text))
async def process_broadcast_text(message: Message, state: FSMContext):
    """Process broadcast message text."""
    if not is_admin(message.from_user.id):
        await message.answer(ADMIN_NOT_AUTHORIZED)
        await state.clear()
        return
    
    if not message.text:
        await message.answer("❌ Iltimos, matn yuboring.")
        return
    
    # Validate message length (with media: 1024, without: 4096)
    if len(message.text) > 4096:
        await message.answer("❌ Xabar juda uzun (maksimal 4096 belgi). Qisqartiring.")
        return
    
    # Save the message text
    # Use html_text to preserve the actual formatting used by the admin (bold, links, etc.)
    await state.update_data(message_text=message.html_text)
    await state.set_state(AdminStates.waiting_for_broadcast_media)
    await message.answer(ADMIN_BROADCAST_MEDIA, parse_mode=ParseMode.HTML)


@router.message(Command("skip"), StateFilter(AdminStates.waiting_for_broadcast_media))
async def skip_media(message: Message, state: FSMContext):
    """Skip media upload."""
    await show_target_selection(message, state)


@router.message(Command("done"), StateFilter(AdminStates.waiting_for_broadcast_media))
async def done_media(message: Message, state: FSMContext):
    """Finish media upload."""
    await show_target_selection(message, state)


@router.message(StateFilter(AdminStates.waiting_for_broadcast_media), F.photo | F.video)
async def process_media(message: Message, state: FSMContext):
    """Process media upload (photo or video)."""
    if not is_admin(message.from_user.id):
        await message.answer(ADMIN_NOT_AUTHORIZED)
        await state.clear()
        return
    
    data = await state.get_data()
    media_files = data.get('media_files', [])
    
    # If the user sends a photo right away instead of text, capture its caption
    # as the broadcast text if we don't already have one
    if not data.get('message_text'):
        await state.update_data(message_text=(message.html_text or ""))
    
    if len(media_files) >= 10:
        await message.answer("❌ Maksimal 10 ta media yuklash mumkin. /done bosing.")
        return
    
    # Check message text length if media is added
    message_text = data.get('message_text', '')
    if len(message_text) > 1024:
        await message.answer(
            "❌ Media bilan xabar 1024 belgidan oshmasligi kerak.\n"
            "Xabaringiz {len(message_text)} belgi. Iltimos, qisqartiring.\n\n"
            "/cancel bosib qaytadan boshlang."
        )
        return
    
    # Save media info
    if message.photo:
        # Get largest photo
        photo = message.photo[-1]
        media_info = {
            'type': 'photo',
            'file_id': photo.file_id,
            'file_unique_id': photo.file_unique_id,
        }
    elif message.video:
        video = message.video
        media_info = {
            'type': 'video',
            'file_id': video.file_id,
            'file_unique_id': video.file_unique_id,
            'duration': video.duration,
            'width': video.width,
            'height': video.height,
            'thumb_file_id': video.thumbnail.file_id if video.thumbnail else None,
        }
    else:
        return
    
    media_files.append(media_info)
    await state.update_data(media_files=media_files)
    
    await message.answer(
        ADMIN_MEDIA_ADDED.format(count=len(media_files)),
        parse_mode=ParseMode.HTML
    )


async def show_target_selection(message: Message, state: FSMContext):
    """Show target selection screen."""
    data = await state.get_data()
    message_text = data.get('message_text', '')
    media_files = data.get('media_files', [])
    selected_targets = data.get('selected_targets', {})
    
    # Format media info
    media_info = ""
    if media_files:
        media_types = {}
        for mf in media_files:
            mtype = mf['type']
            media_types[mtype] = media_types.get(mtype, 0) + 1
        
        media_parts = []
        if media_types.get('photo'):
            media_parts.append(f"{media_types['photo']} ta rasm")
        if media_types.get('video'):
            media_parts.append(f"{media_types['video']} ta video")
        media_info = f"<b>Media:</b> {', '.join(media_parts)}\n\n"
    
    # Format current targets
    current_targets = format_selected_targets(selected_targets)
    
    from html import escape
    preview_text = message_text[:200] + "..." if len(message_text) > 200 else message_text
    
    text = ADMIN_BROADCAST_TARGET.format(
        message=escape(preview_text),
        media_info=media_info,
        current_targets=current_targets
    )
    
    await state.set_state(AdminStates.waiting_for_broadcast_confirmation)
    await message.answer(
        text,
        reply_markup=get_target_keyboard(selected_targets),
        parse_mode=ParseMode.HTML
    )


def format_selected_targets(selected_targets: dict) -> str:
    """Format selected targets as text."""
    if not selected_targets or not any(selected_targets.values()):
        return "<i>Hali tanlanmagan</i>"
    
    parts = []
    if selected_targets.get('all_users'):
        return "Barcha foydalanuvchilar"
    
    grades = [g for g in [5, 6, 7, 8] if selected_targets.get(f'grade_{g}')]
    if grades:
        parts.append(f"{', '.join(map(str, grades))}-sinflar")
    
    if selected_targets.get('not_fully_registered'):
        parts.append("To'liq ro'yxatdan o'tmaganlarga")
    
    if selected_targets.get('include_reg_btn'):
        parts.append("Ro'yxatdan o'tish tugmasi bilan")
    
    return ", ".join(parts) if parts else "<i>Hali tanlanmagan</i>"


@router.callback_query(F.data.startswith("target_"))
async def handle_target_toggle(callback: CallbackQuery, state: FSMContext):
    """Handle target selection toggle."""
    data = await state.get_data()
    selected_targets = data.get('selected_targets', {})
    
    action = callback.data.replace("target_", "")
    
    if action == "all":
        # Toggle all users
        selected_targets['all_users'] = not selected_targets.get('all_users', False)
        # If all users selected, clear other selections
        if selected_targets['all_users']:
            for key in list(selected_targets.keys()):
                if key != 'all_users':
                    selected_targets[key] = False
    
    elif action.startswith("grade_"):
        grade = action.replace("grade_", "")
        key = f'grade_{grade}'
        selected_targets[key] = not selected_targets.get(key, False)
        # Clear all users if individual grade selected
        if selected_targets[key]:
            selected_targets['all_users'] = False
    
    elif action == "not_reg":
        selected_targets['not_fully_registered'] = not selected_targets.get('not_fully_registered', False)
        # Clear all users if this is selected
        if selected_targets['not_fully_registered']:
            selected_targets['all_users'] = False
            
    elif action == "include_reg_btn":
        selected_targets['include_reg_btn'] = not selected_targets.get('include_reg_btn', False)
    
    elif action == "done":
        # Validate selection
        if not any(selected_targets.values()):
            await callback.answer(ADMIN_NO_TARGETS, show_alert=True)
            return
        
        await state.update_data(selected_targets=selected_targets)
        await show_confirmation(callback.message, state)
        await callback.answer()
        return
    
    elif action == "cancel":
        await state.clear()
        await callback.message.edit_text(ADMIN_BROADCAST_CANCELLED)
        await callback.answer()
        return
    
    await state.update_data(selected_targets=selected_targets)
    
    # Update keyboard
    message_text = data.get('message_text', '')
    media_files = data.get('media_files', [])
    
    media_info = ""
    if media_files:
        media_types = {}
        for mf in media_files:
            mtype = mf['type']
            media_types[mtype] = media_types.get(mtype, 0) + 1
        
        media_parts = []
        if media_types.get('photo'):
            media_parts.append(f"{media_types['photo']} ta rasm")
        if media_types.get('video'):
            media_parts.append(f"{media_types['video']} ta video")
        media_info = f"<b>Media:</b> {', '.join(media_parts)}\n\n"
    
    current_targets = format_selected_targets(selected_targets)
    
    from html import escape
    preview_text = message_text[:200] + "..." if len(message_text) > 200 else message_text

    text = ADMIN_BROADCAST_TARGET.format(
        message=escape(preview_text),
        media_info=media_info,
        current_targets=current_targets
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_target_keyboard(selected_targets),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


async def show_confirmation(message: Message, state: FSMContext):
    """Show confirmation screen."""
    data = await state.get_data()
    message_text = data.get('message_text', '')
    media_files = data.get('media_files', [])
    selected_targets = data.get('selected_targets', {})
    
    # Format media info
    media_info = ""
    if media_files:
        media_types = {}
        for mf in media_files:
            mtype = mf['type']
            media_types[mtype] = media_types.get(mtype, 0) + 1
        
        media_parts = []
        if media_types.get('photo'):
            media_parts.append(f"{media_types['photo']} ta rasm")
        if media_types.get('video'):
            media_parts.append(f"{media_types['video']} ta video")
        media_info = f"<b>Media:</b> {', '.join(media_parts)}\n\n"
    
    # Get recipient count
    recipient_count = await get_recipient_count(selected_targets)
    
    from html import escape
    preview_text = message_text[:300] + "..." if len(message_text) > 300 else message_text

    text = ADMIN_BROADCAST_CONFIRM.format(
        message=escape(preview_text),
        media_info=media_info,
        targets=format_selected_targets(selected_targets),
        recipient_count=recipient_count
    )
    
    await message.edit_text(
        text,
        reply_markup=get_confirmation_keyboard(),
        parse_mode=ParseMode.HTML
    )


@sync_to_async
def get_recipient_count(selected_targets: dict) -> int:
    """Calculate recipient count based on filters."""
    if selected_targets.get('all_users'):
        return Student.objects.filter(is_active=True).count()
    
    queryset = Student.objects.filter(is_active=True)
    
    # Grade filters
    grades = [g for g in [5, 6, 7, 8] if selected_targets.get(f'grade_{g}')]
    if grades:
        queryset = queryset.filter(grade__in=grades)
    
    # Not fully registered filter
    if selected_targets.get('not_fully_registered'):
        from django.db.models import Q
        # A user IS fully registered when they have filled in the reg-app required
        # fields: first_name, last_name, and phone_number.
        from admin_panel.registration_filters import filter_students_by_registration_step
        admin_ids = list(getattr(settings, 'ADMIN_IDS', []))
        fully_registered = filter_students_by_registration_step(Student.objects.all(), 'fully_registered')
        queryset = queryset.exclude(
            Q(pk__in=fully_registered.values_list('pk', flat=True)) | 
            Q(telegram_id__in=admin_ids)
        )
    
    # If no filters selected, return 0
    if not grades and not selected_targets.get('not_fully_registered'):
        return 0
    
    return queryset.count()


@router.callback_query(F.data.startswith("confirm_"))
async def handle_confirmation(callback: CallbackQuery, state: FSMContext):
    """Handle confirmation actions."""
    action = callback.data.replace("confirm_", "")
    
    if action == "send":
        await callback.answer()
        await send_broadcast(callback.message, state)
    
    elif action == "back":
        await callback.answer()
        await show_target_selection(callback.message, state)
    
    elif action == "cancel":
        await state.clear()
        await callback.message.edit_text(ADMIN_BROADCAST_CANCELLED)
        await callback.answer()


async def send_broadcast(message: Message, state: FSMContext):
    """Create broadcast and trigger sending."""
    data = await state.get_data()
    message_text = data.get('message_text', '')
    media_files = data.get('media_files', [])
    selected_targets = data.get('selected_targets', {})
    
    @sync_to_async
    def create_broadcast():
        """Create broadcast message in database."""
        # Create broadcast
        broadcast = BroadcastMessage.objects.create(
            target_all_users=selected_targets.get('all_users', False),
            target_grade_5=selected_targets.get('grade_5', False),
            target_grade_6=selected_targets.get('grade_6', False),
            target_grade_7=selected_targets.get('grade_7', False),
            target_grade_8=selected_targets.get('grade_8', False),
            target_not_fully_registered=selected_targets.get('not_fully_registered', False),
            include_register_button=selected_targets.get('include_reg_btn', False),
            message=message_text,
            status='draft'
        )
        
        # Save media files
        for idx, media_info in enumerate(media_files):
            from aiogram import Bot
            import asyncio
            
            # Download file
            bot = Bot(token=settings.BOT_TOKEN)
            
            async def download_file():
                file = await bot.get_file(media_info['file_id'])
                file_path = file.file_path
                
                # Download to media directory
                media_dir = os.path.join(settings.MEDIA_ROOT, 'broadcasts')
                os.makedirs(media_dir, exist_ok=True)
                
                # Generate filename
                ext = os.path.splitext(file_path)[1]
                filename = f"{broadcast.id}_{idx}_{media_info['file_unique_id']}{ext}"
                destination = os.path.join(media_dir, filename)
                
                await bot.download_file(file_path, destination)
                await bot.session.close()
                
                return f"broadcasts/{filename}"
            
            # Run download
            file_relative_path = asyncio.run(download_file())
            
            # Create BroadcastMedia
            media_obj = BroadcastMedia.objects.create(
                broadcast=broadcast,
                media_type=media_info['type'],
                file=file_relative_path,
                order=idx,
                duration=media_info.get('duration'),
                width=media_info.get('width'),
                height=media_info.get('height'),
            )
            
            # Download thumbnail if exists
            if media_info.get('thumb_file_id'):
                async def download_thumb():
                    bot_thumb = Bot(token=settings.BOT_TOKEN)
                    file_thumb = await bot_thumb.get_file(media_info['thumb_file_id'])
                    thumb_path = file_thumb.file_path
                    
                    thumb_dir = os.path.join(settings.MEDIA_ROOT, 'broadcasts', 'thumbs')
                    os.makedirs(thumb_dir, exist_ok=True)
                    
                    thumb_ext = os.path.splitext(thumb_path)[1]
                    thumb_filename = f"{broadcast.id}_{idx}_thumb{thumb_ext}"
                    thumb_destination = os.path.join(thumb_dir, thumb_filename)
                    
                    await bot_thumb.download_file(thumb_path, thumb_destination)
                    await bot_thumb.session.close()
                    
                    return f"broadcasts/thumbs/{thumb_filename}"
                
                thumb_relative_path = asyncio.run(download_thumb())
                media_obj.thumbnail = thumb_relative_path
                media_obj.save()
        
        return broadcast.id
    
    try:
        # Show preparing message
        await message.edit_text(
            "⏳ Xabarnoma tayyorlanmoqda...",
            parse_mode=ParseMode.HTML
        )
        
        broadcast_id = await create_broadcast()
        from exam_bot_admin.webhook import bot
        import asyncio
        asyncio.create_task(BroadcastService.send_broadcast(broadcast_id, bot))
        
        await message.edit_text(
            ADMIN_BROADCAST_SUCCESS.format(broadcast_id=broadcast_id),
            parse_mode=ParseMode.HTML
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error creating broadcast: {e}", exc_info=True)
        await message.edit_text(
            f"❌ Xatolik yuz berdi: {str(e)}",
            parse_mode=ParseMode.HTML
        )
        await state.clear()



@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Show bot statistics (admin only)."""
    if not is_admin(message.from_user.id):
        await message.answer(ADMIN_NOT_AUTHORIZED)
        return
    
    from admin_panel.models import TestAttempt
    
    @sync_to_async
    def get_stats():
        """Get statistics from database."""
        total_users = Student.objects.count()
        active_users = Student.objects.filter(is_active=True).count()
        
        # Count fully registered
        from django.db.models import Q
        fully_registered_count = Student.objects.filter(
            is_active=True,
            first_name__gt='',
        ).filter(
            Q(last_name__isnull=False) & ~Q(last_name=''),
        ).filter(
            date_of_birth__isnull=False,
            document_number__isnull=False,
            document_number__gt='',
        ).filter(
            parent__isnull=False,
        ).filter(
            Q(parent__phone_number__gt='') | Q(parent__phone_number2__gt=''),
        ).filter(
            teacher__isnull=False,
            teacher__phone_number__gt='',
        ).count()
        
        test_attempts = TestAttempt.objects.count()
        
        # Grade breakdown
        grade_5 = Student.objects.filter(is_active=True, grade=5).count()
        grade_6 = Student.objects.filter(is_active=True, grade=6).count()
        grade_7 = Student.objects.filter(is_active=True, grade=7).count()
        grade_8 = Student.objects.filter(is_active=True, grade=8).count()
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'fully_registered': fully_registered_count,
            'test_attempts': test_attempts,
            'grade_5': grade_5,
            'grade_6': grade_6,
            'grade_7': grade_7,
            'grade_8': grade_8,
        }
    
    try:
        stats = await get_stats()
        
        stats_text = (
            "📊 <b>Bot statistikasi</b>\n\n"
            f"👥 Jami foydalanuvchilar: {stats['total_users']}\n"
            f"✅ Faol foydalanuvchilar: {stats['active_users']}\n"
            f"📝 To'liq ro'yxatdan o'tganlar: {stats['fully_registered']}\n"
            f"📊 Test topshirishlar: {stats['test_attempts']}\n\n"
            f"<b>Sinflar bo'yicha:</b>\n"
            f"• 5-sinf: {stats['grade_5']}\n"
            f"• 6-sinf: {stats['grade_6']}\n"
            f"• 7-sinf: {stats['grade_7']}\n"
            f"• 8-sinf: {stats['grade_8']}\n"
        )
        
        await message.answer(stats_text, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        await message.answer(f"❌ Xatolik yuz berdi: {str(e)}")


@router.message(Command("backup"))
async def cmd_backup(message: Message):
    """Send a JSON backup of the database to the requesting admin."""
    if not is_admin(message.from_user.id):
        await message.answer(ADMIN_NOT_AUTHORIZED)
        return

    status_msg = await message.answer("⏳ Ma'lumotlar bazasi zaxira nusxasi tayyorlanmoqda...")

    try:
        from admin_panel.management.commands.send_db_backup import generate_backup_json
        from aiogram.types import BufferedInputFile
        from datetime import datetime

        @sync_to_async
        def _generate():
            return generate_backup_json()

        json_bytes, stats = await _generate()

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"backup_{timestamp}.json"

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

        await message.answer_document(
            document=BufferedInputFile(json_bytes, filename=filename),
            caption=caption,
            parse_mode=ParseMode.HTML,
        )
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Backup command error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Zaxira nusxa yaratishda xatolik: {e}")


@router.message(Command("send_certificates"))
async def cmd_send_certificates(message: Message, state: FSMContext):
    """Preview and confirm certificate sending for submitted participants."""
    if not is_admin(message.from_user.id):
        await message.answer(ADMIN_NOT_AUTHORIZED)
        return

    command_args = (message.text or "").split()
    if len(command_args) > 1:
        try:
            test_ids = [int(arg) for arg in command_args[1:]]
        except ValueError:
            await message.answer("❌ Barcha test ID lar raqam bo'lishi kerak.", parse_mode=ParseMode.HTML)
            return
    else:
        test_ids = CERTIFICATE_TEST_IDS

    await state.clear()
    status_msg = await message.answer(
        f"⏳ {', '.join(map(str, test_ids))}-testlar bo'yicha sertifikat oluvchilar tayyorlanmoqda..."
    )

    try:
        recipients, error_msg = await collect_certificate_recipients(test_ids)
        if error_msg:
            await status_msg.edit_text(f"❌ {error_msg}")
            return

        if not recipients:
            await status_msg.edit_text("❌ Berilgan testlar bo'yicha topshirgan o'quvchilar topilmadi.")
            return

        preview_path, preview_student_name, preview_test_title = await generate_certificate_preview(
            recipients[0]['attempt_id']
        )

        await state.set_state(AdminStates.waiting_for_certificate_confirmation)
        await state.update_data(
            certificate_attempt_ids=[recipient['attempt_id'] for recipient in recipients],
            certificate_test_ids=test_ids,
        )

        preview_abs_path = Path(settings.MEDIA_ROOT) / preview_path
        await message.answer_document(
            document=FSInputFile(str(preview_abs_path)),
            caption=(
                "🎓 <b>Sertifikat preview</b>\n"
                f"O'quvchi: {preview_student_name}\n"
                f"Test: {preview_test_title}"
            ),
            parse_mode=ParseMode.HTML,
        )

        await status_msg.edit_text(
            "📨 <b>Sertifikat yuborish tasdig'i</b>\n\n"
            f"Test ID lar: {', '.join(map(str, test_ids))}\n"
            f"Qabul qiluvchilar soni: <b>{len(recipients)}</b>\n\n"
            "Yuborishni tasdiqlaysizmi?",
            reply_markup=get_certificate_confirmation_keyboard(),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.error("Send certificates command error: %s", e, exc_info=True)
        await state.clear()
        await status_msg.edit_text(f"❌ Sertifikatlarni tayyorlashda xatolik: {e}")


@router.callback_query(StateFilter(AdminStates.waiting_for_certificate_confirmation), F.data.startswith("certbulk_"))
async def handle_certificate_confirmation(callback: CallbackQuery, state: FSMContext):
    """Handle certificate bulk send confirmation."""
    if not is_admin(callback.from_user.id):
        await callback.answer(ADMIN_NOT_AUTHORIZED, show_alert=True)
        return

    action = callback.data.replace("certbulk_", "")

    if action == "cancel":
        await state.clear()
        await callback.message.edit_text("❌ Sertifikat yuborish bekor qilindi.")
        await callback.answer()
        return

    if action != "send":
        await callback.answer()
        return

    data = await state.get_data()
    attempt_ids = data.get('certificate_attempt_ids', [])
    if not attempt_ids:
        await state.clear()
        await callback.message.edit_text("❌ Yuborish uchun ma'lumot topilmadi. Buyruqni qayta yuboring.")
        await callback.answer()
        return

    await callback.answer()
    await callback.message.edit_text(
        f"⏳ {len(attempt_ids)} ta foydalanuvchiga sertifikat yuborilmoqda...",
        parse_mode=ParseMode.HTML,
    )

    try:
        sent_count, error_count = await send_certificates_to_attempts(attempt_ids)
        await callback.message.edit_text(
            "✅ <b>Sertifikat yuborish yakunlandi</b>\n\n"
            f"Yuborildi: <b>{sent_count}</b>\n"
            f"Xatolar: <b>{error_count}</b>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.error("Certificate bulk send error: %s", e, exc_info=True)
        await callback.message.edit_text(f"❌ Sertifikat yuborishda xatolik: {e}")
    finally:
        await state.clear()


@router.message(F.text.regexp(r"^/teachers[-_]stat(?:@[\w_]+)?$"))
async def cmd_teachers_stat(message: Message):
    """Download teachers ranking as CSV grouped by teacher phone number (admin only)."""
    if not is_admin(message.from_user.id):
        await message.answer(ADMIN_NOT_AUTHORIZED)
        return

    status_msg = await message.answer("⏳ Ustozlar statistikasi tayyorlanmoqda...")

    try:
        from admin_panel.models import Teacher
        from aiogram.types import BufferedInputFile
        from datetime import datetime
        from django.db.models import Count, Max, Q
        import csv
        import io

        @sync_to_async
        def generate_csv_bytes():
            fully_registered_q = Q(student__registered_from_web=True) | (
                Q(student__first_name__gt='') &
                Q(student__last_name__isnull=False) & ~Q(student__last_name='') &
                Q(student__date_of_birth__isnull=False) &
                Q(student__document_number__isnull=False) & ~Q(student__document_number='') &
                Q(student__parent__isnull=False) &
                (~Q(student__parent__phone_number='') | ~Q(student__parent__phone_number2='')) &
                Q(student__teacher__isnull=False) & ~Q(student__teacher__phone_number='')
            )

            teacher_stats = list(
                Teacher.objects.filter(phone_number__isnull=False)
                .exclude(phone_number='')
                .filter(fully_registered_q)
                .values('phone_number')
                .annotate(
                    student_count=Count('student'),
                    full_name=Max('full_name'),
                )
                .filter(student_count__gt=0)
                .order_by('-student_count', 'full_name')
            )

            if not teacher_stats:
                return None, "Ustozlar statistikasi topilmadi."

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                'reyting',
                'ustoz ismi',
                'telefon raqami',
                "o'quvchilar soni",
            ])

            for index, row in enumerate(teacher_stats, 1):
                writer.writerow([
                    index,
                    row.get('full_name') or "",
                    row.get('phone_number') or "",
                    row.get('student_count') or 0,
                ])

            return output.getvalue().encode('utf-8-sig'), None

        csv_bytes, error_msg = await generate_csv_bytes()

        if error_msg:
            await status_msg.edit_text(f"❌ {error_msg}")
            return

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"Ustozlar_statistikasi_{timestamp}.csv"

        await message.answer_document(
            document=BufferedInputFile(csv_bytes, filename=filename),
            caption=f"👨‍🏫 <b>Ustozlar statistikasi</b>\nSana: {timestamp}",
            parse_mode=ParseMode.HTML,
        )
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Teachers stat command error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ustozlar statistikasini yuklashda xatolik: {e}")


@router.message(Command("test_results"))
async def cmd_test_results(message: Message):
    """Download combined test results as CSV for one or more tests (admin only)."""
    if not is_admin(message.from_user.id):
        await message.answer(ADMIN_NOT_AUTHORIZED)
        return

    # Extract test_ids from the command
    command_args = message.text.split()
    if len(command_args) < 2:
        await message.answer(
            "❌ Iltimos, kamida bitta test ID kiriting. Misol: /test_results 123 124 125",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        test_ids = [int(arg) for arg in command_args[1:]]
    except ValueError:
        await message.answer("❌ Barcha test ID lar raqam bo'lishi kerak.", parse_mode=ParseMode.HTML)
        return

    status_msg = await message.answer(
        f"⏳ {', '.join(map(str, test_ids))}-testlar bo'yicha natijalar yig'ilmoqda..."
    )

    try:
        from admin_panel.models import TestAttempt, Test
        from aiogram.types import BufferedInputFile
        from datetime import datetime
        import csv
        import io
        from django.db.models import Count
        from django.utils import timezone

        def _get_correct_filter(tid):
            from django.db.models import Q

            # Test 17 exception: consider answers for questions 18 and 25 correct
            if tid == 17:
                return Q(answers__is_correct=True) | Q(answers__question__question_number__in=[18, 25])
            return Q(answers__is_correct=True)

        @sync_to_async
        def generate_csv_bytes(tids):
            tests = list(Test.objects.filter(id__in=tids))
            found_test_ids = {test.id for test in tests}
            missing_ids = [tid for tid in tids if tid not in found_test_ids]
            if missing_ids:
                return None, None, f"Quyidagi test ID lar topilmadi: {', '.join(map(str, missing_ids))}."

            tests_by_id = {test.id: test for test in tests}
            total_questions_by_test = {
                test.id: test.questions.count()
                for test in tests
            }

            # Create an in-memory string buffer for CSV
            output = io.StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow([
                'test id',
                'test nomi',
                'Ismi',
                'Familiyasi',
                'til',
                'sinfi',
                'maktabi',
                'viloyati',
                'telefon nomer',
                'seriya raqam',
                "tog'ri javoblar soni",
                "tog'ri javoblar foizi",
                'ustozi ismi',
                'ustozi telefon raqami',
                'test boshlagan vaqt',
                'testni yakunlagan vaqt',
            ])

            written_rows = 0

            for tid in tids:
                test = tests_by_id[tid]
                attempts = TestAttempt.objects.filter(
                    test_id=tid,
                    status='SUBMITTED_FINAL'
                ).select_related('student', 'student__teacher', 'test').annotate(
                    correct_answers=Count('answers', filter=_get_correct_filter(tid))
                )

                total_questions = total_questions_by_test[tid]

                for attempt in attempts:
                    student = attempt.student
                    correct_ans = attempt.correct_answers
                    correct_percent = round((correct_ans / total_questions) * 100, 2) if total_questions else 0
                    teacher = getattr(student, 'teacher', None)

                    started_at = timezone.localtime(attempt.started_at).strftime("%Y-%m-%d %H:%M:%S") if attempt.started_at else ""
                    submitted_at = timezone.localtime(attempt.submitted_at).strftime("%Y-%m-%d %H:%M:%S") if attempt.submitted_at else ""

                    writer.writerow([
                        test.id,
                        test.title,
                        student.first_name or "",
                        student.last_name or "",
                        attempt.test.language or "",
                        student.grade or "",
                        student.school_name or "",
                        student.region or "",
                        student.phone_number or "",
                        student.document_number or "",
                        correct_ans,
                        f"{correct_percent}%",
                        teacher.full_name if teacher else "",
                        teacher.phone_number if teacher else "",
                        started_at,
                        submitted_at,
                    ])
                    written_rows += 1

            if written_rows == 0:
                return None, None, "Berilgan testlar bo'yicha yakuniy natijalar topilmadi."
                
            # Convert to bytes
            csv_bytes = output.getvalue().encode('utf-8-sig') # Add BOM for Excel compatibility
            titles = [tests_by_id[tid].title for tid in tids]
            return csv_bytes, titles, None

        csv_bytes, test_titles, error_msg = await generate_csv_bytes(test_ids)

        if error_msg:
            await status_msg.edit_text(f"❌ {error_msg}")
            return

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"Natijalar_{'_'.join(map(str, test_ids))}_{timestamp}.csv"
        title_preview = ", ".join(test_titles[:3])
        if len(test_titles) > 3:
            title_preview += "..."

        caption = (
            f"📊 <b>Birlashtirilgan test natijalari</b>\n"
            f"Testlar: {title_preview}\n"
            f"ID lar: {', '.join(map(str, test_ids))}\n"
            f"Sana: {timestamp}"
        )

        await message.answer_document(
            document=BufferedInputFile(csv_bytes, filename=filename),
            caption=caption,
            parse_mode=ParseMode.HTML,
        )
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Test results command error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Natijalarni yuklashda xatolik: {e}")


@router.message(Command("help_admin"))
async def cmd_help_admin(message: Message):
    """Show admin commands (admin only)."""
    if not is_admin(message.from_user.id):
        await message.answer(ADMIN_NOT_AUTHORIZED)
        return
    
    help_text = (
        "🔧 <b>Admin buyruqlari</b>\n\n"
        "/broadcast - Xabarnoma yuborish (media qo'llab-quvvatlash bilan)\n"
        "/stats - Bot statistikasi\n"
        "/backup - Ma'lumotlar bazasi zaxira nusxasini yuborish\n"
        "/teachers_stat - Ustozlar statistikasini CSV formatida yuklash\n"
        "/test_results <id> - Test natijalarini CSV formatida yuklash\n"
        "/send_certificates [id ...] - Test topshirganlarga sertifikat yuborish\n"
        "/help_admin - Admin buyruqlari ro'yxati\n"
        "/cancel - Joriy amalni bekor qilish\n\n"
        "<b>Broadcast jarayoni:</b>\n"
        "1. Xabar matnini yuboring\n"
        "2. Media yuklang (ixtiyoriy)\n"
        "3. Maqsadni tanlang (sinf, holat)\n"
        "4. Tasdiqlang va yuboring\n"
    )
    
    await message.answer(help_text, parse_mode=ParseMode.HTML)
