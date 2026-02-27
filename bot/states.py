"""FSM states for bot."""
from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Registration flow states."""
    # Stage 1: Initial Link
    waiting_for_initial_full_name = State()
    waiting_for_initial_phone = State()
    waiting_for_phone_owner = State()
    waiting_for_webapp_reg = State()  # After 3 steps: user opens Web App form

    # Post-Registration / Promo
    waiting_for_olympiad_participation = State() # Yes/No


    # Confirmation and Editing
    waiting_for_confirmation = State()
    waiting_for_channels = State()                 # Join channels at end of registration
    waiting_for_post_reg_promo = State()            # Post-registration
    waiting_for_edit_field = State()
    editing_field = State()


class TestStates(StatesGroup):
    """Test flow states."""
    selecting_language = State()
    selecting_test = State()
    waiting_for_start_confirmation = State()
    answering_question = State()
    reviewing_answers = State()
    editing_answer = State()
    waiting_for_final_submission = State()


class FeedbackStates(StatesGroup):
    """Feedback flow states."""
    waiting_for_type = State()
    waiting_for_text = State()


class AdminStates(StatesGroup):
    """Admin command flow states."""
    waiting_for_broadcast_text = State()
    waiting_for_broadcast_media = State()
    waiting_for_broadcast_confirmation = State()
