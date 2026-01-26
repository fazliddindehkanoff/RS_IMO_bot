"""FSM states for bot."""
from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Registration flow states."""
    # Step 1: Student Information
    waiting_for_first_name = State()
    waiting_for_last_name = State()
    waiting_for_middle_name = State()
    waiting_for_date_of_birth = State()
    waiting_for_document_number = State()
    waiting_for_region = State()
    waiting_for_district = State()
    waiting_for_school_name = State()
    waiting_for_grade = State()
    waiting_for_language = State()
    waiting_for_photo = State()
    waiting_for_achievements_description = State()
    waiting_for_achievements_file = State()
    
    # Step 2: Guardian Information
    waiting_for_guardian_name = State()
    waiting_for_guardian_relationship = State()
    waiting_for_guardian_age = State()
    waiting_for_guardian_children_count = State()
    waiting_for_guardian_profession = State()
    waiting_for_guardian_phone1 = State()
    waiting_for_guardian_phone2 = State()
    
    # Step 3: Teacher Information
    waiting_for_teacher_name = State()
    waiting_for_teacher_workplace = State()
    waiting_for_teacher_phone = State()
    
    # Step 4: Source
    waiting_for_registration_source = State()
    waiting_for_source_details = State()
    
    # Confirmation and Editing
    waiting_for_confirmation = State()
    waiting_for_edit_field = State()
    editing_field = State()


class TestStates(StatesGroup):
    """Test flow states."""
    waiting_for_start_confirmation = State()
    answering_question = State()
    reviewing_answers = State()
    editing_answer = State()
    waiting_for_final_submission = State()
