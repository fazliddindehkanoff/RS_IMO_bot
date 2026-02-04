from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.states import FeedbackStates
from bot.keyboards import get_feedback_type_keyboard, get_main_menu_keyboard
from bot.services import FeedbackService, StudentService

router = Router()

@router.message(F.text == "💬 Fikr bildirish")
async def cmd_feedback(message: Message, state: FSMContext):
    """Start feedback flow."""
    await state.set_state(FeedbackStates.waiting_for_type)
    await message.answer(
        "Fikr bildirish turini tanlang:",
        reply_markup=get_feedback_type_keyboard()
    )

@router.callback_query(FeedbackStates.waiting_for_type, F.data.startswith("feedback_"))
async def process_feedback_type(callback: CallbackQuery, state: FSMContext):
    """Process feedback type selection."""
    feedback_type = callback.data.split("_")[1] # suggestion or complaint
    
    await state.update_data(feedback_type=feedback_type)
    await state.set_state(FeedbackStates.waiting_for_text)
    
    type_text = "Taklif" if feedback_type == "suggestion" else "Shikoyat"
    await callback.message.edit_text(
        f"Siz {type_text} tanladingiz.\n\n"
        "Iltimos, fikringizni yozib qoldiring:"
    )

@router.message(FeedbackStates.waiting_for_text)
async def process_feedback_text(message: Message, state: FSMContext):
    """Process feedback text."""
    data = await state.get_data()
    feedback_type = data.get("feedback_type")
    
    student = await StudentService.get_student(message.from_user.id)
    if not student:
        await message.answer("Siz avval ro'yxatdan o'tishingiz kerak.")
        await state.clear()
        return

    await FeedbackService.create_feedback(
        student=student,
        feedback_type=feedback_type,
        text=message.text
    )
    
    await state.clear()
    await message.answer(
        "Rahmat! Fikringiz qabul qilindi.",
        reply_markup=get_main_menu_keyboard()
    )
