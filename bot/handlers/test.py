"""Test handlers for user test flow."""
import logging
from typing import Optional

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile, InputMediaPhoto
from django.utils import timezone
from datetime import timedelta

from bot.states import TestStates
from bot.keyboards import (
    get_start_test_keyboard,
    get_test_selection_keyboard,
    get_language_selection_keyboard,
    get_start_confirmation_keyboard,
    get_answer_keyboard,
    get_no_answer_confirmation_keyboard,
    get_review_keyboard,
    get_question_list_keyboard,
    get_final_submission_keyboard,
    get_test_completion_keyboard,
    get_main_menu_keyboard,
)
from bot.services import StudentService, TestService, BotStateService
from admin_panel.models import TestAttempt, Test

logger = logging.getLogger(__name__)

router = Router()


# ==================== TEST SENDING (5.1) ====================

async def send_test_to_user(message: Message, student, test):
    """Send test notification message to user."""
    grade_label = (
        dict(test.GRADE_CHOICES).get(test.grade, "Test")
        if test.grade is not None
        else "Test"
    )

    text = (
        f"Hurmatli {student.first_name}, sizga {grade_label} grant imtihoni savollari yuborildi.\n\n"
        f"Vaqt: {test.duration_minutes} daqiqa. Yakuniy topshirish 1 marta."
    )

    await message.answer(
        text,
        reply_markup=get_start_test_keyboard(test_id=test.id)
    )


@router.message(F.text == "📊 Imtihonlar")
async def handle_imtihonlar(message: Message, state: FSMContext):
    """Show test info and Boshlash when user taps Imtihonlar from main menu."""
    telegram_id = message.from_user.id
    student = await StudentService.get_student(telegram_id)

    if not student or not student.grade:
        await message.answer("❌ Avval ro'yxatdan o'ting!")
        return

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
        test = pending.test
        await send_test_to_user(message, student, test)
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
        
        # Get all active tests for grade (language selection handled below)
        tests = await TestService.get_active_tests_for_grade_and_language(
            student.grade,
            None
        )

        if not tests:
            await message.answer("❌ Sizning sinfingiz uchun test topilmadi.")
            return

        languages = sorted({test.language for test in tests if test.language})
        if len(languages) > 1:
            language_labels = dict(Test.LANGUAGE_CHOICES)
            await message.answer(
                "Iltimos, test tilini tanlang:",
                reply_markup=get_language_selection_keyboard(languages, language_labels)
            )
            await state.set_state(TestStates.selecting_language)
            return

        if len(tests) == 1:
            # Only one test - show it directly
            await send_test_to_user(message, student, tests[0])
        else:
            # Multiple tests - show selection keyboard
            text = "Iltimos, test tanlang:"
            await message.answer(
                text,
                reply_markup=get_test_selection_keyboard(tests)
            )
            await state.set_state(TestStates.selecting_test)


# ==================== TEST SELECTION (5.1.5) ====================

@router.callback_query(F.data.startswith("test_lang_"))
async def handle_test_language_selection(callback: CallbackQuery, state: FSMContext):
    """Handle test language selection."""
    telegram_id = callback.from_user.id
    student = await StudentService.get_student(telegram_id)

    if not student or not student.grade:
        await callback.answer("❌ Avval ro'yxatdan o'ting!", show_alert=True)
        return

    # Extract language from callback data
    language = callback.data.split("_")[-1]
    tests = await TestService.get_active_tests_for_grade_and_language(
        student.grade,
        language
    )

    if not tests:
        await callback.answer("❌ Test topilmadi!", show_alert=True)
        return

    if len(tests) == 1:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await send_test_to_user(callback.message, student, tests[0])
        await state.clear()
        return

    try:
        await callback.message.edit_text(
            "Iltimos, test tanlang:",
            reply_markup=get_test_selection_keyboard(tests)
        )
    except Exception:
        await callback.message.answer(
            "Iltimos, test tanlang:",
            reply_markup=get_test_selection_keyboard(tests)
        )

    await state.set_state(TestStates.selecting_test)

@router.callback_query(StateFilter(TestStates.selecting_test), F.data.startswith("test_select_"))
async def handle_test_selection(callback: CallbackQuery, state: FSMContext):
    """Handle test selection from multiple available tests."""
    telegram_id = callback.from_user.id
    student = await StudentService.get_student(telegram_id)
    
    if not student:
        await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)
        return
    
    # Extract test ID from callback data
    try:
        test_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)
        return
    
    # Get the selected test
    test = await TestService.get_test_by_id(test_id)
    
    if not test or not test.is_active:
        await callback.answer("❌ Test topilmadi yoki faol emas!", show_alert=True)
        return
    
    # Verify the test is available for this student's grade
    if test.grade != student.grade:
        await callback.answer("❌ Bu test sizning sinf darajangiz uchun emas!", show_alert=True)
        return
    
    # Show the selected test
    await callback.message.delete()
    await send_test_to_user(callback.message, student, test)
    await state.clear()


# ==================== START CONFIRMATION (5.2) ====================

@router.callback_query(F.data.startswith("test_start"))
async def handle_test_start(callback: CallbackQuery, state: FSMContext):
    """Handle test start button click."""
    telegram_id = callback.from_user.id
    student = await StudentService.get_student(telegram_id)

    if not student or not student.grade:
        await callback.answer("❌ Avval ro'yxatdan o'ting!", show_alert=True)
        return

    # Extract test_id from callback data if provided (e.g., "test_start_123")
    test_id_from_callback = None
    if callback.data.startswith("test_start_"):
        try:
            test_id_from_callback = int(callback.data.split("_")[-1])
        except (ValueError, IndexError):
            pass

    # Prefer assigned (PENDING) attempt from admin "send test"
    pending = await TestService.get_pending_attempt_for_student(student)
    if pending:
        test = pending.test
        attempt = pending
        # Check if already submitted
        if attempt.status == 'SUBMITTED_FINAL':
            await callback.answer(
                "✅ Siz allaqachon bu testni topshirgansiz. Natijalarni tez orada e'lon qilamiz!",
                show_alert=True
            )
            return
        # Check not already in progress
        if attempt.status == 'IN_PROGRESS':
            await callback.answer("⚠️ Sizda allaqachon davom etayotgan test bor!", show_alert=True)
            return
    else:
        # If test_id is provided from callback, use it
        if test_id_from_callback:
            test = await TestService.get_test_by_id(test_id_from_callback)
            if not test:
                await callback.answer("❌ Test topilmadi!", show_alert=True)
                return
        else:
            # Otherwise, get the first active test for the grade and language
            tests = await TestService.get_active_tests_for_grade_and_language(
                student.grade,
                student.language
            )
            if not tests:
                await callback.answer("❌ Sizning sinfingiz uchun test topilmadi!", show_alert=True)
                return
            test = tests[0]

        existing_attempt = await TestService.get_active_attempt_for_student(student, test)
        if existing_attempt:
            if existing_attempt.status == 'SUBMITTED_FINAL':
                await callback.answer(
                    "✅ Siz allaqachon bu testni topshirgansiz. Natijalarni tez orada e'lon qilamiz!",
                    show_alert=True
                )
                return
            if existing_attempt.status == 'IN_PROGRESS':
                await callback.answer("⚠️ Sizda allaqachon davom etayotgan test bor!", show_alert=True)
                return

        attempt = await TestService.create_test_attempt(student, test)

    # Check if test is within the valid time range
    current_time = timezone.now()
    if test.starts_at and current_time < test.starts_at:
        await callback.answer(
            "❌ Test hali boshlanmadi. Iltimos, keyinroq urinib ko'ring.",
            show_alert=True
        )
        return
    
    if test.finish_at and current_time > test.finish_at:
        await callback.answer(
            "❌ Test vaqti tugab qolgan. Siz test boshlay olmaysiz.",
            show_alert=True
        )
        return

    await state.update_data(attempt_id=attempt.id, test_id=test.id)
    await BotStateService.update_state_data(telegram_id, attempt_id=attempt.id, test_id=test.id)

    try:
        await callback.message.edit_text(
            "Testni boshlashni tasdiqlaysizmi?",
            reply_markup=get_start_confirmation_keyboard()
        )
    except Exception:
        # If message can't be edited (e.g., already deleted), send a new message
        await callback.message.answer(
            "Testni boshlashni tasdiqlaysizmi?",
            reply_markup=get_start_confirmation_keyboard()
        )
    
    await callback.answer()
    await state.set_state(TestStates.waiting_for_start_confirmation)


@router.callback_query(StateFilter(TestStates.waiting_for_start_confirmation), F.data == "test_confirm_start")
async def confirm_test_start(callback: CallbackQuery, state: FSMContext):
    """Confirm test start."""
    await callback.message.delete()
    telegram_id = callback.from_user.id
    data = await state.get_data()
    attempt_id = data.get('attempt_id')
    
    if not attempt_id:
        await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)
        return
    
    # Start the attempt
    attempt = await TestService.start_test_attempt(attempt_id)
    
    # Get first question
    questions = await TestService.get_questions_for_test(attempt.test)
    if not questions:
        await callback.answer("❌ Testda savollar topilmadi!", show_alert=True)
        return
    
    first_question = questions[0]
    
    # Show first question (edits confirmation message)
    await show_question(callback.message, attempt, first_question, 1, len(questions), callback=callback)
    
    await callback.answer()
    await state.set_state(TestStates.answering_question)
    await BotStateService.set_state(telegram_id, "answering_question", {
        'attempt_id': attempt_id,
        'test_id': attempt.test.id,
        'current_question': 1,
    })


@router.callback_query(StateFilter(TestStates.waiting_for_start_confirmation), F.data == "test_cancel_start")
async def cancel_test_start(callback: CallbackQuery, state: FSMContext):
    """Cancel test start."""
    await callback.message.edit_text("Test bekor qilindi.")
    await callback.answer()
    await state.clear()
    await BotStateService.clear_state(callback.from_user.id)


# ==================== QUESTIONS + NAVIGATION (5.3, 5.4) ====================

def _question_has_image(question) -> bool:
    """Return True if question has an uploaded image file."""
    return bool(question.image and question.image.name)


async def show_question(message: Message, attempt: TestAttempt, question, question_number: int, total_questions: int, callback: CallbackQuery = None):
    """Show question with answer options.
    
    If the question has an image, the image is sent with the text as caption.
    
    Args:
        message: Message object (used for sending new messages)
        attempt: TestAttempt instance
        question: TestQuestion instance
        question_number: Current question number
        total_questions: Total number of questions
        callback: Optional CallbackQuery - if provided, edits existing message instead of sending new one
    """
    # Get existing answer if any
    existing_answer = await TestService.get_answer(attempt, question)
    current_answer = existing_answer.answer_choice if existing_answer else None
    
    # Check if all questions are answered (for showing finish button during editing)
    all_answers = await TestService.get_all_answers(attempt)
    all_questions_answered = len(all_answers) == total_questions and all(a.answer_choice for a in all_answers)
    
    # Build question text (plain text)
    text = f"Savol {question_number}/{total_questions}\n\n"
    
    # Add question text if it exists
    if question.text:
        text += f"{question.text}\n\n"
    
    # Add options (only if they exist)
    options = question.get_options_dict()
    for choice, option_text in options.items():
        if option_text:  # Only include non-empty options
            marker = "✅ " if current_answer == choice else ""
            text += f"{marker}{choice}. {option_text}\n"
    
    # Add time remaining if started
    if attempt.started_at and attempt.expires_at:
        remaining = attempt.get_remaining_time_minutes()
        if remaining is not None:
            text += f"\n⏱️ Qolgan vaqt: {remaining} daqiqa"
    
    # Check if expired
    if attempt.is_expired():
        text += "\n\n⚠️ Vaqt tugadi!"
    
    # Build keyboard
    has_previous = question_number > 1
    has_next = question_number < total_questions
    keyboard = get_answer_keyboard(question_number, total_questions, has_previous, has_next, current_answer, show_finish=all_questions_answered)
    
    has_image = _question_has_image(question)

    # Edit existing message if callback provided, otherwise send new message
    if callback:
        message_has_photo = callback.message.photo is not None and len(callback.message.photo) > 0

        if message_has_photo and has_image:
            # Both photo: edit media to update the actual photo
            try:
                media = InputMediaPhoto(
                    media=FSInputFile(question.image.path),
                    caption=text,
                    parse_mode="HTML" if "<" in text else None
                )
                await callback.message.edit_media(
                    media=media,
                    reply_markup=keyboard,
                )
            except Exception as e:
                # Fallback: send new photo if edit_media fails
                from exam_bot_admin.webhook import bot
                try:
                    await callback.message.delete()
                except Exception:
                    pass
                photo_file = FSInputFile(question.image.path)
                await bot.send_photo(
                    chat_id=message.chat.id,
                    photo=photo_file,
                    caption=text,
                    reply_markup=keyboard,
                )
        elif not message_has_photo and not has_image:
            # Both text: edit text
            try:
                await callback.message.edit_text(
                    text=text,
                    reply_markup=keyboard,
                )
            except Exception:
                await message.answer(text, reply_markup=keyboard)
        else:
            # Type switch (photo↔text): delete old and send new message
            from exam_bot_admin.webhook import bot
            try:
                await callback.message.delete()
            except Exception:
                pass
            
            if has_image:
                photo_file = FSInputFile(question.image.path)
                await bot.send_photo(
                    chat_id=message.chat.id,
                    photo=photo_file,
                    caption=text,
                    reply_markup=keyboard,
                )
            else:
                await message.answer(text, reply_markup=keyboard)
    else:
        # Send new message
        if has_image:
            from exam_bot_admin.webhook import bot
            photo_file = FSInputFile(question.image.path)
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=photo_file,
                caption=text,
                reply_markup=keyboard,
            )
        else:
            await message.answer(text, reply_markup=keyboard)


@router.callback_query(StateFilter(TestStates.answering_question), F.data.startswith("test_answer_"))
async def handle_answer(callback: CallbackQuery, state: FSMContext):
    """Handle answer selection."""
    # Check time limit first
    if not await check_time_limit_before_action(callback, state):
        return
    
    answer_choice = callback.data.split("_")[-1]
    telegram_id = callback.from_user.id
    data = await state.get_data()
    attempt_id = data.get('attempt_id')
    
    if not attempt_id:
        await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)
        return
    
    attempt = await TestService.get_test_attempt(attempt_id)
    if not attempt:
        await callback.answer("❌ Test topilmadi!", show_alert=True)
        return
    
    # Check if expired
    if attempt.is_expired():
        await callback.answer("⚠️ Vaqt tugadi!", show_alert=True)
        return
    
    # Get current question
    current_question_num = data.get('current_question', 1)
    question = await TestService.get_question_by_number(attempt.test, current_question_num)
    
    if not question:
        await callback.answer("❌ Savol topilmadi!", show_alert=True)
        return
    
    # Save answer
    await TestService.save_answer(attempt, question, answer_choice)
    
    # Get all questions
    questions = await TestService.get_questions_for_test(attempt.test)
    total_questions = len(questions)
    
    # Edit existing question message with updated answer
    await show_question(callback.message, attempt, question, current_question_num, total_questions, callback=callback)
    
    await callback.answer(f"✅ {answer_choice} tanlandi")


@router.callback_query(StateFilter(TestStates.answering_question), F.data == "test_next")
async def handle_next_question(callback: CallbackQuery, state: FSMContext):
    """Handle next question navigation."""
    # Check time limit first
    if not await check_time_limit_before_action(callback, state):
        return
    
    telegram_id = callback.from_user.id
    data = await state.get_data()
    attempt_id = data.get('attempt_id')
    current_question_num = data.get('current_question', 1)
    
    if not attempt_id:
        await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)
        return
    
    attempt = await TestService.get_test_attempt(attempt_id)
    if not attempt:
        await callback.answer("❌ Test topilmadi!", show_alert=True)
        return
    
    # Check if expired
    if attempt.is_expired():
        await callback.answer("⚠️ Vaqt tugadi!", show_alert=True)
        return
    
    # Get all questions
    questions = await TestService.get_questions_for_test(attempt.test)
    total_questions = len(questions)
    
    # Check if answer exists for current question
    current_question = questions[current_question_num - 1]
    existing_answer = await TestService.get_answer(attempt, current_question)
    
    # If no answer selected, show warning but continue
    if not existing_answer or not existing_answer.answer_choice:
        await callback.answer("⚠️ Bu savol javobsiz qoldi", show_alert=True)
    
    # Move to next question
    next_question_num = current_question_num + 1
    
    if next_question_num > total_questions:
        # Last question - should not happen here, but handle it
        await callback.answer("❌ Bu oxirgi savol!", show_alert=True)
        return
    
    next_question = questions[next_question_num - 1]
    
    # Update state
    await state.update_data(current_question=next_question_num)
    await BotStateService.update_state_data(telegram_id, current_question=next_question_num)
    
    # Show next question (edits current message)
    await show_question(callback.message, attempt, next_question, next_question_num, total_questions, callback=callback)
    await callback.answer()


@router.callback_query(StateFilter(TestStates.answering_question), F.data == "test_prev")
async def handle_prev_question(callback: CallbackQuery, state: FSMContext):
    """Handle previous question navigation."""
    # Check time limit first
    if not await check_time_limit_before_action(callback, state):
        return
    
    telegram_id = callback.from_user.id
    data = await state.get_data()
    attempt_id = data.get('attempt_id')
    current_question_num = data.get('current_question', 1)
    
    if not attempt_id:
        await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)
        return
    
    attempt = await TestService.get_test_attempt(attempt_id)
    if not attempt:
        await callback.answer("❌ Test topilmadi!", show_alert=True)
        return
    
    # Check if expired
    if attempt.is_expired():
        await callback.answer("⚠️ Vaqt tugadi!", show_alert=True)
        return
    
    # Get all questions
    questions = await TestService.get_questions_for_test(attempt.test)
    total_questions = len(questions)
    
    # Check if answer exists for current question
    current_question = questions[current_question_num - 1]
    existing_answer = await TestService.get_answer(attempt, current_question)
    
    # If no answer selected, show warning but continue
    if not existing_answer or not existing_answer.answer_choice:
        await callback.answer("⚠️ Bu savol javobsiz qoldi", show_alert=True)
    
    # Move to previous question
    prev_question_num = current_question_num - 1
    
    if prev_question_num < 1:
        await callback.answer("❌ Bu birinchi savol!", show_alert=True)
        return
    
    prev_question = questions[prev_question_num - 1]
    
    # Update state
    await state.update_data(current_question=prev_question_num)
    await BotStateService.update_state_data(telegram_id, current_question=prev_question_num)
    
    # Show previous question (edit current message)
    await show_question(callback.message, attempt, prev_question, prev_question_num, total_questions, callback=callback)
    await callback.answer()


@router.callback_query(StateFilter(TestStates.answering_question), F.data == "test_continue_no_answer")
async def continue_without_answer(callback: CallbackQuery, state: FSMContext):
    """Continue to next/previous question without answer."""
    # Check time limit first
    if not await check_time_limit_before_action(callback, state):
        return
    
    telegram_id = callback.from_user.id
    data = await state.get_data()
    attempt_id = data.get('attempt_id')
    current_question_num = data.get('current_question', 1)
    nav_direction = data.get('nav_direction', 'next')  # Default to 'next' for backwards compatibility
    
    attempt = await TestService.get_test_attempt(attempt_id)
    questions = await TestService.get_questions_for_test(attempt.test)
    total_questions = len(questions)
    
    if nav_direction == 'prev':
        # Move to previous question
        prev_question_num = current_question_num - 1
        
        if prev_question_num < 1:
            await callback.answer("❌ Bu birinchi savol!", show_alert=True)
            return
        
        prev_question = questions[prev_question_num - 1]
        
        # Update state
        await state.update_data(current_question=prev_question_num, nav_direction=None)
        await BotStateService.update_state_data(telegram_id, current_question=prev_question_num)
        
        # Show previous question (edit confirmation message)
        await show_question(callback.message, attempt, prev_question, prev_question_num, total_questions, callback=callback)
    else:
        # Move to next question
        next_question_num = current_question_num + 1
        
        if next_question_num > total_questions:
            # Last question - go to finish
            await handle_finish(callback, state)
            return
        
        next_question = questions[next_question_num - 1]
        
        # Update state
        await state.update_data(current_question=next_question_num, nav_direction=None)
        await BotStateService.update_state_data(telegram_id, current_question=next_question_num)
        
        # Show next question (edit confirmation message)
        await show_question(callback.message, attempt, next_question, next_question_num, total_questions, callback=callback)
    
    await callback.answer()


@router.callback_query(StateFilter(TestStates.answering_question), F.data == "test_back_no_answer")
async def back_from_no_answer(callback: CallbackQuery, state: FSMContext):
    """Go back to question from no answer confirmation."""
    telegram_id = callback.from_user.id
    data = await state.get_data()
    attempt_id = data.get('attempt_id')
    current_question_num = data.get('current_question', 1)
    
    attempt = await TestService.get_test_attempt(attempt_id)
    questions = await TestService.get_questions_for_test(attempt.test)
    total_questions = len(questions)
    current_question = questions[current_question_num - 1]
    
    # Show question again (edit confirmation message)
    await show_question(callback.message, attempt, current_question, current_question_num, total_questions, callback=callback)
    await callback.answer()


# ==================== FINISH (5.5) ====================

@router.callback_query(StateFilter(TestStates.answering_question), F.data == "test_finish")
async def handle_finish(callback: CallbackQuery, state: FSMContext):
    """Handle finish button (last question)."""
    # Check time limit first
    if not await check_time_limit_before_action(callback, state):
        return
    
    telegram_id = callback.from_user.id
    data = await state.get_data()
    attempt_id = data.get('attempt_id')
    current_question_num = data.get('current_question', 1)
    
    attempt = await TestService.get_test_attempt(attempt_id)
    
    # Check if expired
    if attempt.is_expired():
        await callback.answer("⚠️ Vaqt tugadi!", show_alert=True)
        return
    
    # Check if answer exists for current question
    questions = await TestService.get_questions_for_test(attempt.test)
    current_question = questions[current_question_num - 1]
    existing_answer = await TestService.get_answer(attempt, current_question)
    
    if not existing_answer or not existing_answer.answer_choice:
        # No answer selected - show confirmation via edit
        try:
            await callback.message.edit_text(
                "Javob tanlanmadi. Davom etamizmi?",
                reply_markup=get_no_answer_confirmation_keyboard()
            )
        except Exception:
            # If edit fails, send new message
            await callback.message.answer(
                "Javob tanlanmadi. Davom etamizmi?",
                reply_markup=get_no_answer_confirmation_keyboard()
            )
        await callback.answer()
        return
    
    # Delete the question message before showing review
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    # Finish review
    await TestService.finish_review(attempt_id)
    
    # Show review page
    await show_review_page(callback.message, attempt)
    
    await callback.answer()
    await state.set_state(TestStates.reviewing_answers)
    await BotStateService.set_state(telegram_id, "reviewing_answers", {'attempt_id': attempt_id})


# ==================== REVIEW PAGE (5.6) ====================

async def show_review_page(message: Message, attempt: TestAttempt):
    """Show review page with all answers."""
    questions = await TestService.get_questions_for_test(attempt.test)
    answers = await TestService.get_all_answers(attempt)
    
    # Create answer map
    answer_map = {a.question.id: a for a in answers}
    
    text = "<b>📋 Tekshiruv sahifasi</b>\n\n"
    
    for question in questions:
        answer = answer_map.get(question.id)
        answer_text = answer.answer_choice if answer and answer.answer_choice else "—"
        text += f"• {question.question_number}-savol: {answer_text}\n"
    
    await message.answer(text, reply_markup=get_review_keyboard(), parse_mode="HTML")


@router.callback_query(StateFilter(TestStates.reviewing_answers), F.data == "test_edit_answers")
async def handle_edit_answers(callback: CallbackQuery, state: FSMContext):
    """Handle edit answers button."""
    telegram_id = callback.from_user.id
    data = await state.get_data()
    attempt_id = data.get('attempt_id')
    
    attempt = await TestService.get_test_attempt(attempt_id)
    questions = await TestService.get_questions_for_test(attempt.test)
    answers = await TestService.get_all_answers(attempt)
    
    # Create answer map
    answer_map = {a.question.id: a for a in answers}
    
    # Add answer_choice to questions for keyboard
    for question in questions:
        answer = answer_map.get(question.id)
        question.answer_choice = answer.answer_choice if answer and answer.answer_choice else None
    
    await callback.message.edit_text(
        "Qaysi savolni tahrirlamoqchisiz?",
        reply_markup=get_question_list_keyboard(questions)
    )
    await callback.answer()
    await state.set_state(TestStates.editing_answer)


@router.callback_query(StateFilter(TestStates.editing_answer), F.data.startswith("test_edit_q_"))
async def handle_edit_question(callback: CallbackQuery, state: FSMContext):
    """Handle question selection for editing."""
    question_number = int(callback.data.split("_")[-1])
    telegram_id = callback.from_user.id
    data = await state.get_data()
    attempt_id = data.get('attempt_id')
    
    attempt = await TestService.get_test_attempt(attempt_id)
    question = await TestService.get_question_by_number(attempt.test, question_number)
    questions = await TestService.get_questions_for_test(attempt.test)
    total_questions = len(questions)
    
    # Update state
    await state.update_data(current_question=question_number)
    await BotStateService.update_state_data(telegram_id, current_question=question_number)
    
    # Delete the question list message and send the question
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    # Show question for editing (send as new message, not edit)
    await show_question(callback.message, attempt, question, question_number, total_questions, callback=None)
    
    await callback.answer()
    await state.set_state(TestStates.answering_question)


@router.callback_query(StateFilter(TestStates.editing_answer), F.data == "test_back_to_review")
async def back_to_review(callback: CallbackQuery, state: FSMContext):
    """Go back to review page."""
    telegram_id = callback.from_user.id
    data = await state.get_data()
    attempt_id = data.get('attempt_id')
    
    attempt = await TestService.get_test_attempt(attempt_id)
    
    await show_review_page(callback.message, attempt)
    
    await callback.answer()
    await state.set_state(TestStates.reviewing_answers)


# ==================== FINAL SUBMISSION (5.7) ====================

@router.callback_query(StateFilter(TestStates.reviewing_answers), F.data == "test_submit_final")
async def handle_submit_final(callback: CallbackQuery, state: FSMContext):
    """Handle final submission button."""
    await callback.message.edit_text(
        "Yakuniy topshirsangiz, javoblar o'zgarmaydi. Tasdiqlaysizmi?",
        reply_markup=get_final_submission_keyboard()
    )
    await callback.answer()
    await state.set_state(TestStates.waiting_for_final_submission)


@router.callback_query(StateFilter(TestStates.waiting_for_final_submission), F.data == "test_confirm_submit")
async def confirm_final_submit(callback: CallbackQuery, state: FSMContext):
    """Confirm final submission."""
    telegram_id = callback.from_user.id
    data = await state.get_data()
    attempt_id = data.get('attempt_id')
    
    attempt = await TestService.submit_final(attempt_id)
    
    text = (
        "<b>🎉 Tabriklaymiz, testni muvaffaqiyatli yakunladingiz!</b>\n\n"
        "🏆 Kanalimizda umumiy natijalarni tez kunda e’lon qilamiz, kuzatishda davom eting:\n\n@rs_olimpiada"
    )
    
    await callback.message.edit_text(text, reply_markup=get_test_completion_keyboard())
    await callback.answer()
    
    await state.clear()
    await BotStateService.clear_state(telegram_id)


@router.callback_query(StateFilter(TestStates.waiting_for_final_submission), F.data == "test_back_from_submit")
async def back_from_submit(callback: CallbackQuery, state: FSMContext):
    """Go back from final submission confirmation."""
    telegram_id = callback.from_user.id
    data = await state.get_data()
    attempt_id = data.get('attempt_id')
    
    attempt = await TestService.get_test_attempt(attempt_id)
    
    await show_review_page(callback.message, attempt)
    
    await callback.answer()
    await state.set_state(TestStates.reviewing_answers)


# ==================== TIME LIMIT (5.8) ====================

async def check_time_limit_before_action(callback: CallbackQuery, state: FSMContext) -> bool:
    """Check time limit before processing any test callback. Returns True if should continue."""
    data = await state.get_data()
    attempt_id = data.get('attempt_id')
    
    if attempt_id:
        attempt = await TestService.get_test_attempt(attempt_id)
        if attempt and attempt.is_expired() and attempt.status in ['IN_PROGRESS', 'FINISHED_REVIEW']:
            # Expire the attempt
            await TestService.expire_attempt(attempt_id, auto_submit=False)
            
            await callback.message.answer("⚠️ Vaqt tugadi.")
            await callback.answer("⚠️ Vaqt tugadi!", show_alert=True)
            
            await state.clear()
            await BotStateService.clear_state(callback.from_user.id)
            return False
    
    return True


# ==================== COMPLETION ACTIONS ====================

@router.callback_query(F.data == "test_suggestions")
async def handle_suggestions(callback: CallbackQuery):
    """Handle suggestions button."""
    await callback.answer("Takliflar bo'limi tez orada qo'shiladi!", show_alert=True)


@router.callback_query(F.data == "test_complaints")
async def handle_complaints(callback: CallbackQuery):
    """Handle complaints button."""
    await callback.answer("Shikoyatlar bo'limi tez orada qo'shiladi!", show_alert=True)
