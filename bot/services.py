"""Service layer for database operations."""
from typing import Optional
from django.db import transaction
from django.utils import timezone
from asgiref.sync import sync_to_async

from admin_panel.models import (
    Student, Parent, Teacher, RegistrationSource, BotState,
    Test, TestQuestion, TestAttempt, TestAnswer, Referral,
    MandatoryChannel
)
from datetime import timedelta


class StudentService:
    """Service for student operations."""
    
    @staticmethod
    @sync_to_async
    def get_or_create_student(telegram_id: int, username: Optional[str] = None):
        """Get or create student by telegram_id."""
        with transaction.atomic():
            student, created = Student.objects.get_or_create(
                telegram_id=telegram_id,
                defaults={
                    'username': username,
                    'first_name': '',
                    'is_active': True,
                    'referral_code': str(telegram_id),
                }
            )
            if not student.referral_code:
                student.referral_code = str(telegram_id)
                student.save(update_fields=['referral_code'])
            return student, created
    
    @staticmethod
    @sync_to_async
    def update_student(telegram_id: int, **kwargs):
        """Update student fields."""
        with transaction.atomic():
            student = Student.objects.get(telegram_id=telegram_id)
            for key, value in kwargs.items():
                if value is not None:
                    setattr(student, key, value)
            student.save()
            return student
    
    @staticmethod
    @sync_to_async
    def get_student(telegram_id: int):
        """Get student by telegram_id."""
        try:
            return Student.objects.get(telegram_id=telegram_id)
        except Student.DoesNotExist:
            return None
    
    @staticmethod
    @sync_to_async
    def create_parent(student: Student, full_name: str, phone_number: Optional[str] = None, 
                     relationship: Optional[str] = None, age: Optional[int] = None,
                     children_count: Optional[int] = None, profession: Optional[str] = None,
                     phone_number2: Optional[str] = None):
        """Create parent for student."""
        with transaction.atomic():
            parent, _ = Parent.objects.get_or_create(
                student=student,
                defaults={
                    'full_name': full_name,
                    'phone_number': phone_number,
                    'phone_number2': phone_number2,
                    'relationship': relationship,
                    'age': age,
                    'children_count': children_count,
                    'profession': profession,
                }
            )
            return parent
    
    @staticmethod
    @sync_to_async
    def update_parent(student: Student, **kwargs):
        """Update parent fields."""
        with transaction.atomic():
            try:
                parent = Parent.objects.get(student=student)
                for key, value in kwargs.items():
                    if value is not None:
                        setattr(parent, key, value)
                parent.save()
                return parent
            except Parent.DoesNotExist:
                return None
    
    @staticmethod
    @sync_to_async
    def create_teacher(student: Student, full_name: str, phone_number: Optional[str] = None,
                      workplace: Optional[str] = None):
        """Create teacher for student."""
        with transaction.atomic():
            teacher, _ = Teacher.objects.get_or_create(
                student=student,
                defaults={
                    'full_name': full_name,
                    'phone_number': phone_number,
                    'workplace': workplace,
                }
            )
            return teacher
    
    @staticmethod
    @sync_to_async
    def update_teacher(student: Student, **kwargs):
        """Update teacher fields."""
        with transaction.atomic():
            try:
                teacher = Teacher.objects.get(student=student)
                for key, value in kwargs.items():
                    if value is not None:
                        setattr(teacher, key, value)
                teacher.save()
                return teacher
            except Teacher.DoesNotExist:
                return None
    
    @staticmethod
    @sync_to_async
    def create_registration_source(student: Student, source_type: str, 
                                   source_details: Optional[str] = None):
        """Create registration source for student."""
        with transaction.atomic():
            source, _ = RegistrationSource.objects.get_or_create(
                student=student,
                defaults={
                    'source_type': source_type,
                    'source_details': source_details,
                }
            )
            return source
    
    @staticmethod
    @sync_to_async
    def update_registration_source(student: Student, **kwargs):
        """Update registration source fields."""
        with transaction.atomic():
            try:
                source = RegistrationSource.objects.get(student=student)
                for key, value in kwargs.items():
                    if value is not None:
                        setattr(source, key, value)
                source.save()
                return source
            except RegistrationSource.DoesNotExist:
                return None

    @staticmethod
    @sync_to_async
    def get_student_by_referral_code(referral_code: str):
        """Get student by referral code (e.g. telegram_id as string)."""
        if not referral_code:
            return None
        try:
            return Student.objects.get(referral_code=referral_code)
        except Student.DoesNotExist:
            try:
                return Student.objects.get(telegram_id=int(referral_code))
            except (ValueError, Student.DoesNotExist):
                return None

    @staticmethod
    @sync_to_async
    def create_referral_and_award_points(referrer: Student, referred: Student, points: int = 5):
        """Create Referral record and add points to referrer. Idempotent per referred student."""
        with transaction.atomic():
            if Referral.objects.filter(referred=referred).exists():
                return None
            Referral.objects.create(referrer=referrer, referred=referred, points_earned=points)
            referrer.referral_points = (referrer.referral_points or 0) + points
            referrer.save(update_fields=['referral_points'])
            return referrer

    @staticmethod
    @sync_to_async
    def get_referral_leaderboard(limit: int = 10):
        """Get top students by referral_points."""
        return list(
            Student.objects.filter(is_active=True)
            .order_by('-referral_points', '-created_at')
            .values('telegram_id', 'first_name', 'last_name', 'referral_points')[:limit]
        )

    @staticmethod
    @sync_to_async
    def get_user_referral_rank(telegram_id: int):
        """Get current user's rank (1-based) by referral_points. Same order as leaderboard."""
        from django.db.models import Q
        try:
            student = Student.objects.get(telegram_id=telegram_id, is_active=True)
        except Student.DoesNotExist:
            return None
        above = Student.objects.filter(is_active=True).filter(
            Q(referral_points__gt=student.referral_points)
            | Q(referral_points=student.referral_points, created_at__lt=student.created_at)
        ).count()
        return above + 1


class BotStateService:
    """Service for bot state management."""
    
    @staticmethod
    @sync_to_async
    def get_state(telegram_id: int):
        """Get bot state for user."""
        try:
            return BotState.objects.get(telegram_id=telegram_id)
        except BotState.DoesNotExist:
            return None
    
    @staticmethod
    @sync_to_async
    def set_state(telegram_id: int, state: Optional[str], state_data: Optional[dict] = None):
        """Set bot state for user."""
        with transaction.atomic():
            bot_state, _ = BotState.objects.update_or_create(
                telegram_id=telegram_id,
                defaults={
                    'state': state,
                    'state_data': state_data or {},
                    'updated_at': timezone.now(),
                }
            )
            return bot_state
    
    @staticmethod
    @sync_to_async
    def update_state_data(telegram_id: int, **kwargs):
        """Update state data."""
        with transaction.atomic():
            try:
                bot_state = BotState.objects.get(telegram_id=telegram_id)
                if not bot_state.state_data:
                    bot_state.state_data = {}
                bot_state.state_data.update(kwargs)
                bot_state.save()
            except BotState.DoesNotExist:
                BotState.objects.create(
                    telegram_id=telegram_id,
                    state=None,
                    state_data=kwargs,
                )
    
    @staticmethod
    @sync_to_async
    def clear_state(telegram_id: int):
        """Clear bot state."""
        BotState.objects.filter(telegram_id=telegram_id).delete()


class TestService:
    """Service for test operations."""
    
    @staticmethod
    @sync_to_async
    def get_active_test_for_grade(grade: int):
        """Get active test for a grade."""
        try:
            return Test.objects.filter(grade=grade, is_active=True).first()
        except Test.DoesNotExist:
            return None

    @staticmethod
    @sync_to_async
    def get_pending_attempt_for_student(student):
        """Get a PENDING test attempt assigned to this student (e.g. from admin send)."""
        return (
            TestAttempt.objects.filter(
                student=student,
                status='PENDING',
                test__is_active=True,
            )
            .select_related('test')
            .order_by('-created_at')
            .first()
        )
    
    @staticmethod
    @sync_to_async
    def get_test_by_id(test_id: int):
        """Get test by ID."""
        try:
            return Test.objects.get(id=test_id)
        except Test.DoesNotExist:
            return None
    
    @staticmethod
    @sync_to_async
    def create_test_attempt(student: Student, test: Test):
        """Create a new test attempt."""
        with transaction.atomic():
            # Check if there's already an active attempt
            existing = TestAttempt.objects.filter(
                student=student,
                test=test,
                status__in=['PENDING', 'IN_PROGRESS', 'FINISHED_REVIEW']
            ).first()
            
            if existing:
                return existing
            
            # Create new attempt
            started_at = timezone.now()
            expires_at = started_at + timedelta(minutes=test.duration_minutes)
            
            attempt = TestAttempt.objects.create(
                student=student,
                test=test,
                status='PENDING',
                started_at=None,  # Will be set when user confirms
                expires_at=None,  # Will be set when user confirms
            )
            return attempt
    
    @staticmethod
    @sync_to_async
    def start_test_attempt(attempt_id: int):
        """Start the test attempt (set started_at and expires_at)."""
        with transaction.atomic():
            attempt = TestAttempt.objects.get(id=attempt_id)
            if attempt.status == 'PENDING':
                started_at = timezone.now()
                expires_at = started_at + timedelta(minutes=attempt.test.duration_minutes)
                attempt.started_at = started_at
                attempt.expires_at = expires_at
                attempt.status = 'IN_PROGRESS'
                attempt.save()
            return attempt
    
    @staticmethod
    @sync_to_async
    def get_test_attempt(attempt_id: int):
        """Get test attempt by ID."""
        try:
            return TestAttempt.objects.select_related('student', 'test').get(id=attempt_id)
        except TestAttempt.DoesNotExist:
            return None
    
    @staticmethod
    @sync_to_async
    def get_active_attempt_for_student(student: Student, test: Test):
        """Get active test attempt for student."""
        try:
            return TestAttempt.objects.select_related('test').filter(
                student=student,
                test=test,
                status__in=['PENDING', 'IN_PROGRESS', 'FINISHED_REVIEW']
            ).first()
        except TestAttempt.DoesNotExist:
            return None
    
    @staticmethod
    @sync_to_async
    def get_questions_for_test(test: Test):
        """Get all questions for a test ordered by question_number."""
        return list(TestQuestion.objects.filter(test=test).order_by('question_number'))
    
    @staticmethod
    @sync_to_async
    def get_question_by_number(test: Test, question_number: int):
        """Get question by number."""
        try:
            return TestQuestion.objects.get(test=test, question_number=question_number)
        except TestQuestion.DoesNotExist:
            return None
    
    @staticmethod
    @sync_to_async
    def save_answer(attempt: TestAttempt, question: TestQuestion, answer_choice: str):
        """Save or update answer for a question."""
        with transaction.atomic():
            answer, created = TestAnswer.objects.update_or_create(
                attempt=attempt,
                question=question,
                defaults={
                    'answer_choice': answer_choice,
                    'is_correct': (answer_choice == question.correct_answer),
                    'points_earned': question.ball_weight if (answer_choice == question.correct_answer) else 0.0,
                }
            )
            return answer
    
    @staticmethod
    @sync_to_async
    def get_answer(attempt: TestAttempt, question: TestQuestion):
        """Get answer for a question."""
        try:
            return TestAnswer.objects.get(attempt=attempt, question=question)
        except TestAnswer.DoesNotExist:
            return None
    
    @staticmethod
    @sync_to_async
    def get_all_answers(attempt: TestAttempt):
        """Get all answers for an attempt."""
        return list(TestAnswer.objects.filter(attempt=attempt).select_related('question').order_by('question__question_number'))
    
    @staticmethod
    @sync_to_async
    def finish_review(attempt_id: int):
        """Mark attempt as finished review."""
        with transaction.atomic():
            attempt = TestAttempt.objects.get(id=attempt_id)
            attempt.status = 'FINISHED_REVIEW'
            attempt.save()
            return attempt
    
    @staticmethod
    @sync_to_async
    def submit_final(attempt_id: int):
        """Submit test attempt and calculate score."""
        with transaction.atomic():
            attempt = TestAttempt.objects.select_related('test').get(id=attempt_id)
            
            # Get all answers
            answers = TestAnswer.objects.filter(attempt=attempt).select_related('question')
            
            # Calculate scores
            total_points = sum(q.ball_weight for q in attempt.test.questions.all())
            earned_points = sum(a.points_earned for a in answers)
            score = (earned_points / total_points * 100) if total_points > 0 else 0
            
            # Update attempt
            attempt.status = 'SUBMITTED_FINAL'
            attempt.submitted_at = timezone.now()
            attempt.total_points = total_points
            attempt.earned_points = earned_points
            attempt.score = score
            attempt.save()
            
            return attempt
    
    @staticmethod
    @sync_to_async
    def check_and_expire_attempts():
        """Check and expire attempts that have exceeded time limit."""
        with transaction.atomic():
            now = timezone.now()
            expired_attempts = TestAttempt.objects.filter(
                status__in=['IN_PROGRESS', 'FINISHED_REVIEW'],
                expires_at__lt=now
            )
            
            for attempt in expired_attempts:
                attempt.status = 'TIME_EXPIRED'
                attempt.save()
            
            return list(expired_attempts)
    
    @staticmethod
    @sync_to_async
    def expire_attempt(attempt_id: int, auto_submit: bool = False):
        """Expire an attempt, optionally auto-submitting."""
        with transaction.atomic():
            attempt = TestAttempt.objects.get(id=attempt_id)
            
            if auto_submit:
                # Auto-submit with current answers
                answers = TestAnswer.objects.filter(attempt=attempt).select_related('question')
                total_points = sum(q.ball_weight for q in attempt.test.questions.all())
                earned_points = sum(a.points_earned for a in answers)
                score = (earned_points / total_points * 100) if total_points > 0 else 0
                
                attempt.status = 'SUBMITTED_FINAL'
                attempt.submitted_at = timezone.now()
                attempt.total_points = total_points
                attempt.earned_points = earned_points
                attempt.score = score
            else:
                attempt.status = 'TIME_EXPIRED'
            
            attempt.save()
            return attempt


import asyncio
import time

class SubscriptionService:
    """Service for checking channel subscriptions."""
    
    _CHANNEL_CACHE = None
    _CACHE_TIMESTAMP = 0
    _CACHE_TIMEOUT = 300  # 5 minutes


    @staticmethod
    @sync_to_async
    def get_mandatory_channels():
        """Get list of active mandatory channels (cached)."""
        now = time.time()
        if (SubscriptionService._CHANNEL_CACHE is None or 
            now - SubscriptionService._CACHE_TIMESTAMP > SubscriptionService._CACHE_TIMEOUT):
            
            SubscriptionService._CHANNEL_CACHE = list(MandatoryChannel.objects.filter(is_active=True))
            SubscriptionService._CACHE_TIMESTAMP = now
            
        return SubscriptionService._CHANNEL_CACHE

    @staticmethod
    async def _check_single_channel(bot, user_id: int, channel) -> bool:
        """Check subscription for a single channel. Returns True if subscribed/verified."""
        try:
            # Add @ if username and not numeric ID
            chat_id = channel.channel_id
            if not chat_id.startswith('-') and not chat_id.startswith('@') and not chat_id.isdigit():
                chat_id = f"@{chat_id}"
            
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            return member.status not in ['left', 'kicked']
        except Exception:
            # On error (e.g. bot not admin, or temp network fail), assume subscribed
            # so we don't block the user unnecessarily. 
            return True

    @staticmethod
    async def check_subscription(bot, user_id: int) -> dict:
        """
        Check if user is subscribed to all mandatory channels.
        Returns: {
            'subscribed': bool,
            'missing_channels': list[MandatoryChannel]
        }
        """
        channels = await SubscriptionService.get_mandatory_channels()
        if not channels:
            return {'subscribed': True, 'missing_channels': []}

        # Create tasks for all channels
        tasks = [SubscriptionService._check_single_channel(bot, user_id, ch) for ch in channels]
        
        # Run all checks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        missing = []
        for channel, is_subscribed in zip(channels, results):
            # is_subscribed is either bool (success) or Exception (failure)
            # _check_single_channel catches most exceptions and returns True, 
            # but asyncio.gather catches unhandled ones if return_exceptions=True
            
            if isinstance(is_subscribed, Exception):
                # Critical failure in check logic, assume subscribed (safe fail)
                continue
                
            if not is_subscribed:
                missing.append(channel)
                
        return {
            'subscribed': len(missing) == 0,
            'missing_channels': missing
        }
