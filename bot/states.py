"""FSM states for bot."""
from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Registration flow states."""
    # Stage 1: Initial Link
    waiting_for_initial_full_name = State()
    waiting_for_initial_phone = State()
    waiting_for_phone_owner = State()
    
    # Post-Registration / Promo
    waiting_for_olympiad_participation = State() # Yes/No

    # Stage 2: Olympiad Registration (Steps 1-19)
    # Step 1-10: Student Information
    waiting_for_first_name = State()       # 1
    waiting_for_last_name = State()        # 2
    waiting_for_date_of_birth = State()    # 3
    waiting_for_document_number = State()  # 4
    waiting_for_region = State()           # 5
    waiting_for_district = State()         # 6
    waiting_for_school_name = State()      # 7
    waiting_for_grade = State()            # 8
    waiting_for_language = State()         # 9
    waiting_for_photo = State()            # 10
    waiting_for_achievements_description = State() # 11
    waiting_for_achievements_file = State()        # 12
    waiting_for_guardian_name = State()            # 13
    waiting_for_guardian_relationship = State()    # 14
    waiting_for_guardian_age = State()             # 15
    waiting_for_guardian_profession = State()      # 16
    waiting_for_guardian_phone = State()           # 17
    waiting_for_guardian_phone2 = State()          # 18
    waiting_for_teacher_name = State()             # 19
    waiting_for_teacher_workplace = State()        # 20
    waiting_for_teacher_phone = State()            # 21
    waiting_for_source = State()                   # 22
    
    # Confirmation and Editing
    waiting_for_confirmation = State()
    waiting_for_post_reg_promo = State()           # Post-registration
    waiting_for_edit_field = State()
    editing_field = State()


class TestStates(StatesGroup):
    """Test flow states."""
    waiting_for_start_confirmation = State()
    answering_question = State()
    reviewing_answers = State()
    editing_answer = State()
    waiting_for_final_submission = State()


class FeedbackStates(StatesGroup):
    """Feedback flow states."""
    waiting_for_type = State()
    waiting_for_text = State()
