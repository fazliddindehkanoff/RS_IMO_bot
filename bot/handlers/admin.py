"""Admin command handlers."""
import logging
import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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


@router.message(Command("test_results"))
async def cmd_test_results(message: Message):
    """Download test results as CSV for a specific test (admin only)."""
    if not is_admin(message.from_user.id):
        await message.answer(ADMIN_NOT_AUTHORIZED)
        return

    # Extract test_id from the command
    command_args = message.text.split()
    if len(command_args) != 2:
        await message.answer("❌ Iltimos, test ID sini kiriting. Misol: /test_results 123", parse_mode=ParseMode.HTML)
        return

    try:
        test_id = int(command_args[1])
    except ValueError:
        await message.answer("❌ Test ID si raqam bo'lishi kerak.", parse_mode=ParseMode.HTML)
        return

    status_msg = await message.answer(f"⏳ {test_id}-test bo'yicha natijalar yig'ilmoqda...")

    try:
        from admin_panel.models import TestAttempt, Test
        from aiogram.types import BufferedInputFile
        from datetime import datetime
        import csv
        import io

        @sync_to_async
        def generate_csv_bytes(tid):
            # Check if test exists
            try:
                test = Test.objects.get(id=tid)
            except Test.DoesNotExist:
                return None, None, "Test topilmadi."

            from django.db.models import Count, Q
            
            # Test 17 exception: consider answers for questions 18 and 25 correct
            if tid == 17:
                correct_filter = Q(answers__is_correct=True) | Q(answers__question__question_number__in=[18, 25])
            else:
                correct_filter = Q(answers__is_correct=True)
            
            # Annotate with correct answers count, filtering by SUBMITTED_FINAL
            attempts = TestAttempt.objects.filter(
                test_id=tid, 
                status='SUBMITTED_FINAL'
            ).select_related('student').annotate(
                correct_answers=Count('answers', filter=correct_filter)
            )
            
            if not attempts.exists():
                return None, None, "Ushbu test bo'yicha yakuniy natijalar topilmadi."

            # Create an in-memory string buffer for CSV
            output = io.StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow([
                'Document (*)',
                'Telefon (*)',
                'To\'g\'ri javoblar',
                'Ball'
            ])

            for attempt in attempts:
                student = attempt.student
                doc_num = (student.document_number or "")[-4:] if student.document_number else ""
                doc_masked = f"***{doc_num}" if doc_num else ""
                
                phone_num = (student.phone_number or "")[-4:] if student.phone_number else ""
                phone_masked = f"***{phone_num}" if phone_num else ""
                
                correct_ans = attempt.correct_answers
                score = correct_ans * 2
                
                writer.writerow([
                    doc_masked,
                    phone_masked,
                    correct_ans,
                    score
                ])
                
            # Convert to bytes
            csv_bytes = output.getvalue().encode('utf-8-sig') # Add BOM for Excel compatibility
            return csv_bytes, test.title, None

        csv_bytes, test_title, error_msg = await generate_csv_bytes(test_id)

        if error_msg:
            await status_msg.edit_text(f"❌ {error_msg}")
            return

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        # Clean test title for filename
        clean_title = "".join([c for c in test_title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        clean_title = clean_title.replace(' ', '_')
        filename = f"Natijalar_{test_id}_{clean_title}_{timestamp}.csv"

        caption = (
            f"📊 <b>{test_title}</b> natijalari\n"
            f"ID: {test_id}\n"
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
        "/test_results <id> - Test natijalarini CSV formatida yuklash\n"
        "/help_admin - Admin buyruqlari ro'yxati\n"
        "/cancel - Joriy amalni bekor qilish\n\n"
        "<b>Broadcast jarayoni:</b>\n"
        "1. Xabar matnini yuboring\n"
        "2. Media yuklang (ixtiyoriy)\n"
        "3. Maqsadni tanlang (sinf, holat)\n"
        "4. Tasdiqlang va yuboring\n"
    )
    
    await message.answer(help_text, parse_mode=ParseMode.HTML)
