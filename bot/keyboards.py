"""Keyboard builders for bot."""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

from admin_panel.models import Student


def get_grade_keyboard() -> InlineKeyboardMarkup:
    """Get grade selection keyboard."""
    builder = InlineKeyboardBuilder()
    for value, label in Student.GRADE_CHOICES:
        builder.button(text=label, callback_data=f"grade_{value}")
    builder.button(text="Boshqa sinf", callback_data="grade_other")
    builder.button(text="⬅️ Ortga", callback_data="back")
    builder.adjust(2)
    return builder.as_markup()


def get_region_keyboard() -> InlineKeyboardMarkup:
    """Get region selection keyboard."""
    builder = InlineKeyboardBuilder()
    for value, label in Student.REGION_CHOICES:
        builder.button(text=label, callback_data=f"region_{value}")
    builder.button(text="⬅️ Ortga", callback_data="back")
    builder.adjust(2)
    return builder.as_markup()


def get_language_keyboard() -> InlineKeyboardMarkup:
    """Get language selection keyboard."""
    builder = InlineKeyboardBuilder()
    for value, label in Student.LANGUAGE_CHOICES:
        builder.button(text=label, callback_data=f"language_{value}")
    builder.button(text="⬅️ Ortga", callback_data="back")
    builder.adjust(1)
    return builder.as_markup()


def get_phone_keyboard() -> ReplyKeyboardMarkup:
    """Get phone number sharing keyboard."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="📱 Telefon raqamini yuborish", request_contact=True)
    builder.button(text="⬅️ Ortga")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def get_phone_owner_keyboard() -> InlineKeyboardMarkup:
    """Get phone owner selection keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text="O'zimniki", callback_data="phone_owner_self")
    builder.button(text="Turmush o'rtog'im", callback_data="phone_owner_spouse")
    builder.button(text="Boshqa", callback_data="phone_owner_other")
    builder.button(text="⬅️ Ortga", callback_data="back")
    builder.adjust(1)
    return builder.as_markup()


def get_olympiad_participation_keyboard() -> InlineKeyboardMarkup:
    """Get olympiad participation keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Ha, ro'yxatdan o'tmoqchiman 🔥", callback_data="olympiad_yes")
    builder.button(text="Yo'q, tarqatmoqchiman ⚡️", callback_data="olympiad_no")
    builder.button(text="⬅️ Ortga", callback_data="back")
    builder.adjust(1)
    return builder.as_markup()


def get_skip_keyboard() -> InlineKeyboardMarkup:
    """Get skip button keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⏭️ O'tkazib yuborish", callback_data="skip")
    builder.button(text="⬅️ Ortga", callback_data="back")
    builder.adjust(1)
    return builder.as_markup()


def get_yes_no_keyboard() -> InlineKeyboardMarkup:
    """Get yes/no keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Ha", callback_data="yes")
    builder.button(text="❌ Yo'q", callback_data="no")
    builder.adjust(2)
    return builder.as_markup()


def get_relationship_keyboard() -> InlineKeyboardMarkup:
    """Get relationship type keyboard."""
    from admin_panel.models import Parent
    builder = InlineKeyboardBuilder()
    for value, label in Parent.RELATIONSHIP_CHOICES:
        builder.button(text=label, callback_data=f"relationship_{value}")
    builder.button(text="⬅️ Ortga", callback_data="back")
    builder.adjust(2)
    return builder.as_markup()


def get_children_count_keyboard() -> InlineKeyboardMarkup:
    """Get children count keyboard."""
    from admin_panel.models import Parent
    builder = InlineKeyboardBuilder()
    for value, label in Parent.CHILDREN_COUNT_CHOICES:
        builder.button(text=label, callback_data=f"children_{value}")
    builder.button(text="⬅️ Ortga", callback_data="back")
    builder.adjust(3)
    return builder.as_markup()


def get_source_type_keyboard() -> InlineKeyboardMarkup:
    """Get registration source type keyboard."""
    from admin_panel.models import RegistrationSource
    builder = InlineKeyboardBuilder()
    for value, label in RegistrationSource.SOURCE_TYPE_CHOICES:
        builder.button(text=label, callback_data=f"source_{value}")
    builder.button(text="⬅️ Ortga", callback_data="back")
    builder.adjust(2)
    return builder.as_markup()


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Get back button keyboard (Inline)."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Ortga", callback_data="back")
    return builder.as_markup()


def get_back_reply_keyboard() -> ReplyKeyboardMarkup:
    """Get back button keyboard (Reply)."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="⬅️ Ortga")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Get confirmation keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Tahrirlash", callback_data="edit")
    builder.button(text="✅ Tasdiqlayman", callback_data="confirm")
    builder.adjust(2)
    return builder.as_markup()


def get_edit_fields_keyboard() -> InlineKeyboardMarkup:
    """Get edit fields keyboard."""
    builder = InlineKeyboardBuilder()
    # Student fields
    builder.button(text="Ism", callback_data="edit_field:first_name")
    builder.button(text="Familiya", callback_data="edit_field:last_name")
    builder.button(text="Tug'ilgan sana", callback_data="edit_field:date_of_birth")
    builder.button(text="Metrika raqami", callback_data="edit_field:document_number")
    builder.button(text="Viloyat", callback_data="edit_field:region")
    builder.button(text="Tuman/shahar", callback_data="edit_field:district")
    builder.button(text="Maktab", callback_data="edit_field:school_name")
    builder.button(text="Sinf", callback_data="edit_field:grade")
    # builder.button(text="O'qish tili", callback_data="edit_field:language") # Skipped
    builder.button(text="Foto", callback_data="edit_field:photo")
    builder.button(text="Avvalgi yutuqlar", callback_data="edit_field:achievements_description")
    # builder.button(text="Yutuqlar rasmi", callback_data="edit_field:achievements_file") # Skipped
    
    # Guardian fields
    builder.button(text="Vasiy ismi", callback_data="edit_field:guardian_name")
    builder.button(text="Vasiy kimligi", callback_data="edit_field:guardian_relationship")
    # builder.button(text="Vasiy yoshi", callback_data="edit_field:guardian_age") # Skipped
    # builder.button(text="Vasiy kasbi", callback_data="edit_field:guardian_profession") # Skipped
    builder.button(text="Vasiy tel", callback_data="edit_field:guardian_phone")
    # builder.button(text="Vasiy tel 2", callback_data="edit_field:guardian_phone2") # Skipped
    
    # Teacher fields
    builder.button(text="Ustoz ismi", callback_data="edit_field:teacher_name")
    # builder.button(text="Ustoz ish joyi", callback_data="edit_field:teacher_workplace") # Skipped
    builder.button(text="Ustoz tel", callback_data="edit_field:teacher_phone")
    
    # Other
    builder.button(text="Manba", callback_data="edit_field:source")
    
    builder.button(text="⬅️ Ortga", callback_data="back_to_confirmation")
    builder.adjust(2)
    return builder.as_markup()


def get_post_reg_promo_keyboard() -> InlineKeyboardMarkup:
    """Get post-registration promo keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Ha 🔥", callback_data="accept_promo")
    builder.button(text="⬅️ Ortga", callback_data="back")
    builder.adjust(1)
    return builder.as_markup()


def get_referral_menu_confirm_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for referral menu promo confirmation (Ha → get promo with image)."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Ha 🔥", callback_data="referral_menu_accept")
    builder.button(text="⬅️ Ortga", callback_data="referral_menu_back")
    builder.adjust(1)
    return builder.as_markup()


def get_main_menu_keyboard(other_grade: bool = False) -> ReplyKeyboardMarkup:
    """Get main menu keyboard. If other_grade=True, excludes test button."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="🏆 Konkursda qatnashish")
    if not other_grade:
        builder.button(text="📝 1-bosqich sinov testini yechish: 22-fevral")
    builder.button(text="✏️ Taklif va shikoyatlar")
    builder.button(text="🔥 Konkursdagi ballarim")
    builder.button(text="🏆 Reyting")
    if other_grade:
        builder.adjust(1, 2, 1)
    else:
        builder.adjust(1, 1, 2, 1)
    return builder.as_markup(resize_keyboard=True)


def get_reg_success_keyboard() -> InlineKeyboardMarkup:
    """Three inline buttons after Web App registration: Boshqa menyu, Konkursda qatnashish, Testda qatnashish."""
    from bot.constants import REG_BTN_MAIN_MENU, REG_BTN_PARTICIPATE_CONTEST, REG_BTN_PARTICIPATE_TEST
    builder = InlineKeyboardBuilder()
    builder.button(text=REG_BTN_MAIN_MENU, callback_data="reg_main_menu")
    builder.button(text=REG_BTN_PARTICIPATE_CONTEST, callback_data="reg_participate_contest")
    builder.button(text=REG_BTN_PARTICIPATE_TEST, callback_data="reg_participate_test")
    builder.adjust(1)
    return builder.as_markup()


# ==================== TEST KEYBOARDS ====================

def get_start_test_keyboard(test_id: int = None) -> InlineKeyboardMarkup:
    """Get start test button keyboard.
    
    Args:
        test_id: Optional test ID to include in callback data
    
    Returns:
        InlineKeyboardMarkup with start button
    """
    builder = InlineKeyboardBuilder()
    if test_id:
        builder.button(text="🚀 Boshlash", callback_data=f"test_start_{test_id}")
    else:
        builder.button(text="🚀 Boshlash", callback_data="test_start")
    return builder.as_markup()


def get_test_selection_keyboard(tests) -> InlineKeyboardMarkup:
    """Get test selection keyboard for multiple available tests.
    
    Args:
        tests: List of Test objects
    
    Returns:
        InlineKeyboardMarkup with test selection buttons
    """
    builder = InlineKeyboardBuilder()
    
    for test in tests:
        language_label = test.get_language_display() if getattr(test, 'language', None) else ""
        if language_label:
            button_text = f"{test.title} - {language_label} ({test.duration_minutes} min)"
        else:
            button_text = f"{test.title} ({test.duration_minutes} min)"
        builder.button(text=button_text, callback_data=f"test_select_{test.id}")
    
    builder.adjust(1)
    return builder.as_markup()


def get_language_selection_keyboard(languages, language_labels) -> InlineKeyboardMarkup:
    """Get language selection keyboard for tests.

    Args:
        languages: List of language codes
        language_labels: Dict of language code to label

    Returns:
        InlineKeyboardMarkup with language selection buttons
    """
    builder = InlineKeyboardBuilder()

    for language in languages:
        label = language_labels.get(language, language)
        builder.button(text=label, callback_data=f"test_lang_{language}")

    builder.adjust(2)
    return builder.as_markup()


def get_start_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Get start confirmation keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Ha, boshlayman", callback_data="test_confirm_start")
    builder.button(text="❌ Hozir emas", callback_data="test_cancel_start")
    builder.adjust(2)
    return builder.as_markup()


def get_answer_keyboard(question_number: int, total_questions: int, has_previous: bool = False, has_next: bool = True, current_answer: str = None, show_finish: bool = False) -> InlineKeyboardMarkup:
    """Get answer selection keyboard with navigation."""
    builder = InlineKeyboardBuilder()
    
    # Answer buttons
    answer_labels = {
        'A': 'A',
        'B': 'B',
        'C': 'C',
        'D': 'D',
    }
    
    for choice, label in answer_labels.items():
        # Mark current answer if exists
        text = f"{'✅ ' if current_answer == choice else ''}{label}"
        builder.button(text=text, callback_data=f"test_answer_{choice}")
    
    builder.adjust(2)
    
    # Navigation buttons
    nav_builder = InlineKeyboardBuilder()
    if has_previous:
        nav_builder.button(text="⬅️ Ortga", callback_data="test_prev")
    if has_next:
        nav_builder.button(text="Keyingi ➡️", callback_data="test_next")
    
    # Show finish button if it's the last question OR if all questions are answered (when editing)
    if not has_next or show_finish:
        nav_builder.button(text="✅ Yakunlash", callback_data="test_finish")
    
    nav_builder.adjust(2)
    
    # Combine both builders
    builder.attach(nav_builder)
    return builder.as_markup()


def get_no_answer_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Get confirmation keyboard when no answer selected."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Davom etish", callback_data="test_continue_no_answer")
    builder.button(text="⬅️ Qaytish", callback_data="test_back_no_answer")
    builder.adjust(2)
    return builder.as_markup()


def get_review_keyboard() -> InlineKeyboardMarkup:
    """Get review page keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Javoblarni tahrirlash", callback_data="test_edit_answers")
    builder.button(text="✅ Testni topshirish", callback_data="test_submit_final")
    builder.adjust(1)
    return builder.as_markup()


def get_question_list_keyboard(questions: list, current_question_num: int = None) -> InlineKeyboardMarkup:
    """Get question list keyboard for editing."""
    builder = InlineKeyboardBuilder()
    
    for q in questions:
        # Get answer for this question if exists
        answer_text = "—"
        if hasattr(q, 'answer_choice') and q.answer_choice:
            answer_text = q.answer_choice
        
        text = f"{q.question_number}-savol: {answer_text}"
        if current_question_num and q.question_number == current_question_num:
            text = f"▶️ {text}"
        
        builder.button(text=text, callback_data=f"test_edit_q_{q.question_number}")
    
    builder.button(text="⬅️ Tekshiruvga qaytish", callback_data="test_back_to_review")
    builder.adjust(1)
    return builder.as_markup()


def get_final_submission_keyboard() -> InlineKeyboardMarkup:
    """Get final submission confirmation keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Ha, tasdiqlayman", callback_data="test_confirm_submit")
    builder.button(text="⬅️ Qaytish", callback_data="test_back_from_submit")
    builder.adjust(1)
    return builder.as_markup()


def get_test_completion_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard after test completion."""
    builder = InlineKeyboardBuilder()
    builder.button(text="💡 Takliflar", callback_data="test_suggestions")
    builder.button(text="📢 Shikoyatlar", callback_data="test_complaints")
    builder.adjust(2)
    return builder.as_markup()


def get_feedback_type_keyboard() -> InlineKeyboardMarkup:
    """Get feedback type keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text="💡 Taklif", callback_data="feedback_suggestion")
    builder.button(text="📢 Shikoyat", callback_data="feedback_complaint")
    builder.adjust(2)
    return builder.as_markup()
