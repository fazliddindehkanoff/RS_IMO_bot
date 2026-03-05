"""Aiogram middlewares for the bot."""
import logging
from typing import Any, Awaitable, Callable, Union

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.services import BotStateService, StudentService, SubscriptionService, build_channel_keyboard
from bot.constants import CHECK_SUBS_START

logger = logging.getLogger(__name__)

# States that are part of the on-boarding registration flow.
# Users inside these states are still registering — skip the channel check.
_REGISTRATION_STATES = frozenset({
    "waiting_for_initial_full_name",
    "waiting_for_initial_phone",
    "waiting_for_phone_owner",
    "waiting_for_webapp_reg",
    "waiting_for_olympiad_participation",
    "waiting_for_first_name",
    "waiting_for_last_name",
    "waiting_for_date_of_birth",
    "waiting_for_document_number",
    "waiting_for_region",
    "waiting_for_district",
    "waiting_for_school_name",
    "waiting_for_grade",
    "waiting_for_language",
    "waiting_for_photo",
    "waiting_for_achievements_description",
    "waiting_for_achievements_file",
    "waiting_for_guardian_name",
    "waiting_for_guardian_relationship",
    "waiting_for_guardian_age",
    "waiting_for_guardian_profession",
    "waiting_for_guardian_phone",
    "waiting_for_guardian_phone2",
    "waiting_for_teacher_name",
    "waiting_for_teacher_workplace",
    "waiting_for_teacher_phone",
    "waiting_for_source",
    "waiting_for_confirmation",
    "waiting_for_channels",  # end-of-registration channel check state
    "waiting_for_post_reg_promo",
    "waiting_for_edit_field",
    "editing_field",
})


class ChannelSubscriptionMiddleware(BaseMiddleware):
    """Outer middleware that enforces mandatory channel subscriptions.

    After a user has completed registration, every message and callback is
    intercepted. If the user is not subscribed to all mandatory channels they
    are shown a list of channels to join and the original handler is skipped.

    The check is **skipped** for:
    - Users that haven't started registration yet (no Student record or no
      initial_full_name), so the /start flow still works.
    - Users currently inside any registration FSM state.
    - The ``check_subs`` callback itself, so the "✅ Obunani tekshirish" button
      still works while the user is blocked.
    - Cases where no mandatory channels are configured.
    """

    async def __call__(
        self,
        handler: Callable[[Union[Message, CallbackQuery], dict], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: dict,
    ) -> Any:
        # ── 1. Identify the user ────────────────────────────────────────────
        user = event.from_user
        if not user:
            return await handler(event, data)

        telegram_id = user.id

        # ── 2. Allow the "check_subs" callback to pass always ───────────────
        if isinstance(event, CallbackQuery) and event.data == "check_subs":
            return await handler(event, data)

        # ── 3. Check FSM state — skip if user is still registering ──────────
        state: FSMContext = data.get("state")
        if state:
            current_state = await state.get_state()
            if current_state is not None:
                # Extract just the state name (after the colon separator used by aiogram)
                state_name = current_state.split(":")[-1] if ":" in current_state else current_state
                if state_name in _REGISTRATION_STATES:
                    return await handler(event, data)

        # Also check the persisted BotState in the DB (covers cases where FSM
        # in-memory state was lost but user is mid-registration on another worker).
        bot_state_obj = await BotStateService.get_state(telegram_id)
        if bot_state_obj and bot_state_obj.state in _REGISTRATION_STATES:
            return await handler(event, data)

        # ── 4. Check if user has completed registration ──────────────────────
        # We only enforce the channel check on registered users.
        student = await StudentService.get_student(telegram_id)
        if student is None:
            # Totally new user — let /start handle them.
            return await handler(event, data)

        is_registered = student.registered_from_web or bool(
            student.first_name and student.last_name and student.document_number
        )
        if not is_registered:
            # Not yet registered — let registration flow handle them.
            return await handler(event, data)

        # ── 5. Check mandatory channel subscriptions ─────────────────────────
        bot = data.get("bot") or (event.bot if hasattr(event, "bot") else None)
        if bot is None:
            # Can't check without the bot instance — let the handler proceed.
            return await handler(event, data)

        try:
            status = await SubscriptionService.check_subscription(bot, telegram_id)
        except Exception as exc:
            logger.warning("ChannelSubscriptionMiddleware: check failed for %s: %s", telegram_id, exc)
            # On unexpected error, don't block the user.
            return await handler(event, data)

        if status["subscribed"]:
            # All good — pass through.
            return await handler(event, data)

        # ── 6. User is NOT subscribed — show channel list and block ──────────
        missing = status["missing_channels"]
        keyboard = build_channel_keyboard(missing)

        if isinstance(event, Message):
            await event.answer(CHECK_SUBS_START, reply_markup=keyboard)
        elif isinstance(event, CallbackQuery):
            try:
                await event.message.edit_text(CHECK_SUBS_START, reply_markup=keyboard)
            except Exception:
                await event.message.answer(CHECK_SUBS_START, reply_markup=keyboard)
            try:
                await event.answer()
            except Exception:
                pass

        # Do NOT call handler — block the original action.
        return None
