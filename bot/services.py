"""Service layer for database operations."""
import logging
from html import escape
from typing import Optional

logger = logging.getLogger(__name__)
from django.db import transaction
from django.db.models import Q, Max, F, Count
from django.db.models.functions import Coalesce
from django.utils import timezone
from asgiref.sync import sync_to_async
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from admin_panel.models import (
    Student, Parent, Teacher, RegistrationSource, BotState,
    Test, TestQuestion, TestAttempt, TestAnswer, Referral,
    MandatoryChannel, Feedback, Partner
)
from datetime import timedelta

# Registration state names; when BotState is set to one of these, Student.state is synced too
REGISTRATION_STATE_NAMES = frozenset({
    "waiting_for_initial_full_name", "waiting_for_initial_phone", "waiting_for_phone_owner",
    "waiting_for_webapp_reg",
    "waiting_for_olympiad_participation",
    "waiting_for_first_name", "waiting_for_last_name", "waiting_for_date_of_birth",
    "waiting_for_document_number", "waiting_for_region", "waiting_for_district",
    "waiting_for_school_name", "waiting_for_grade", "waiting_for_language",
    "waiting_for_photo", "waiting_for_achievements_description", "waiting_for_achievements_file",
    "waiting_for_guardian_name", "waiting_for_guardian_relationship", "waiting_for_guardian_age",
    "waiting_for_guardian_profession", "waiting_for_guardian_phone", "waiting_for_guardian_phone2",
    "waiting_for_teacher_name", "waiting_for_teacher_workplace", "waiting_for_teacher_phone",
    "waiting_for_source", "waiting_for_confirmation", "waiting_for_channels",
    "waiting_for_post_reg_promo", "waiting_for_edit_field", "editing_field",
})


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
        """Update student fields. Creates the student if missing (e.g. resume after DB reset or deleted record)."""
        with transaction.atomic():
            student, _ = Student.objects.get_or_create(
                telegram_id=telegram_id,
                defaults={
                    'first_name': '',
                    'is_active': True,
                    'referral_code': str(telegram_id),
                }
            )
            if not student.referral_code:
                student.referral_code = str(telegram_id)
                student.save(update_fields=['referral_code'])
            update_fields = []
            for key, value in kwargs.items():
                if value is not None:
                    setattr(student, key, value)
                    if hasattr(Student, key):
                        update_fields.append(key)
            if update_fields:
                student.save(update_fields=update_fields)
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
    def get_student_by_document_number(document_number: str):
        """Get student by document number (if provided)."""
        if not document_number:
            return None
        try:
            return Student.objects.get(document_number=document_number)
        except Student.DoesNotExist:
            return None

    @staticmethod
    @sync_to_async
    def update_student_webapp(telegram_id: int, username: Optional[str], first_name: str, last_name: str,
                             phone_number: str, region: Optional[str] = None, district: Optional[str] = None,
                             grade: Optional[int] = None, school_name: Optional[str] = None,
                             document_number: Optional[str] = None) -> bool:
        """Create or update student from Web App form. Uses direct UPDATE for reliable persistence. Returns True on success."""
        with transaction.atomic():
            student, created = Student.objects.get_or_create(
                telegram_id=telegram_id,
                defaults={
                    'first_name': (first_name or '').upper()[:255],
                    'last_name': (last_name or '')[:255],
                    'username': username or '',
                    'is_active': True,
                    'referral_code': str(telegram_id),
                }
            )
            if not student.referral_code:
                student.referral_code = str(telegram_id)
                student.save(update_fields=['referral_code'])
            doc_num = (document_number or '').strip().upper()
            update_dict = {
                'username': username or student.username,
                'first_name': (first_name or student.first_name or '').upper()[:255],
                'last_name': (last_name or student.last_name or '')[:255],
                'phone_number': phone_number or student.phone_number,
                'region': region or student.region,
                'district': district or student.district,
                'grade': grade if grade is not None else student.grade,
                'school_name': school_name or student.school_name,
                'document_number': doc_num if doc_num else None,
            }
            Student.objects.filter(telegram_id=telegram_id).update(**update_dict)
        return True

    @staticmethod
    @sync_to_async
    def is_fully_registered(telegram_id: int) -> bool:
        """Check if student has completed full registration (Stage 2 + parent + teacher). Safe to call from async."""
        try:
            student = Student.objects.get(telegram_id=telegram_id)
            return student.is_fully_registered
        except Student.DoesNotExist:
            return False

    @staticmethod
    def infer_registration_state_from_student(student: Student) -> Optional[str]:
        """Infer registration state from student (and related parent/teacher/source) data. Sync only.
        Returns state name or None if fully registered / nothing to resume. Used by backfill script and _infer_registration_state_from_db."""
        if not student:
            return None
        if getattr(student, 'registered_from_web', False):
            return None
        try:
            if student.is_fully_registered:
                return None
        except Exception:
            pass
        try:
            parent = student.parent
        except Parent.DoesNotExist:
            parent = None
        try:
            teacher = student.teacher
        except Exception:
            teacher = None
        try:
            source = student.registration_source
        except Exception:
            source = None

        def _v(s, attr, default=""):
            val = getattr(s, attr, None) if s else None
            return (val or default).strip() if isinstance(val, str) else (val if val is not None else default)

        initial_full_name = _v(student, "initial_full_name")
        phone_number = student.phone_number and str(student.phone_number).strip()
        _po = getattr(student, "phone_owner", None)
        has_phone_owner = bool(_po and str(_po or "").strip())
        first_name = _v(student, "first_name")
        last_name = _v(student, "last_name")
        document_number = _v(student, "document_number")
        region = _v(student, "region")
        district = _v(student, "district")
        school_name = _v(student, "school_name")
        guardian_name = _v(parent, "full_name") if parent else ""
        guardian_relationship = _v(parent, "relationship") if parent else ""
        guardian_phone = _v(parent, "phone_number") if parent else ""
        teacher_name = _v(teacher, "full_name") if teacher else ""
        teacher_phone = _v(teacher, "phone_number") if teacher else ""
        source_type = getattr(source, "source_type", None) if source else ""

        if not initial_full_name:
            return "waiting_for_initial_full_name"
        if not phone_number:
            return "waiting_for_initial_phone"
        if not has_phone_owner:
            return "waiting_for_phone_owner"
        if not first_name:
            return "waiting_for_olympiad_participation"
        if not last_name:
            return "waiting_for_last_name"
        if not student.date_of_birth:
            return "waiting_for_date_of_birth"
        if not document_number:
            return "waiting_for_document_number"
        if not region:
            return "waiting_for_region"
        if not district:
            return "waiting_for_district"
        if not school_name:
            return "waiting_for_school_name"
        if student.grade not in (5, 6, 7, 8):
            return "waiting_for_grade"
        if not (student.photo and str(student.photo).strip()):
            return "waiting_for_photo"
        if not parent or not guardian_name:
            return "waiting_for_guardian_name"
        if not guardian_relationship:
            return "waiting_for_guardian_relationship"
        if not guardian_phone:
            return "waiting_for_guardian_phone"
        if not teacher or not teacher_name:
            return "waiting_for_teacher_name"
        if not teacher_phone:
            return "waiting_for_teacher_phone"
        if not source or not source_type:
            return "waiting_for_source"
        return "waiting_for_confirmation"

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
    def set_referrer(telegram_id: int, referrer: Student):
        """Persistently store who referred this user (when they click /start REF_CODE)."""
        if not referrer or referrer.telegram_id == telegram_id:
            return
        try:
            student = Student.objects.get(telegram_id=telegram_id)
        except Student.DoesNotExist:
            return
        if student.referrer_id is None:
            student.referrer = referrer
            student.save(update_fields=['referrer'])

    @staticmethod
    @sync_to_async
    def get_partner_by_referral_code(code: str):
        """Look up an active Partner by its referral code (ptr_XXXXXXXXXX)."""
        if not code or not code.startswith('ptr_'):
            return None
        try:
            p = Partner.objects.get(referral_code=code, is_active=True)
            logger.info("Partner lookup OK: code=%s -> %s (id=%s)", code, p.name, p.id)
            return p
        except Partner.DoesNotExist:
            all_codes = list(Partner.objects.values_list('referral_code', flat=True)[:10])
            logger.warning(
                "Partner NOT FOUND for code=%s | active partners in DB: %s", code, all_codes
            )
            return None

    @staticmethod
    @sync_to_async
    def set_partner(telegram_id: int, partner: 'Partner'):
        """Assign a partner referral source to a student (once only)."""
        if not partner:
            return
        try:
            student = Student.objects.get(telegram_id=telegram_id)
        except Student.DoesNotExist:
            logger.warning("set_partner: student %s not found", telegram_id)
            return
        if student.partner_id is None:
            student.partner = partner
            student.save(update_fields=['partner'])
            logger.info("Partner %s assigned to student %s", partner.name, telegram_id)
        else:
            logger.info("Student %s already has partner_id=%s, skipping", telegram_id, student.partner_id)

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
    def award_referral_if_pending(telegram_id: int, points: int = 5):
        """
        When registration completes: if student has referrer (stored in DB from /start REF_CODE),
        create Referral, award points to referrer, send notification.
        Idempotent - only runs once per referred student.
        Returns (referrer_telegram_id, referred_name) if award was made, else (None, None).
        """
        try:
            student = Student.objects.select_related('referrer').get(telegram_id=telegram_id)
        except Student.DoesNotExist:
            return None, None
        referrer = student.referrer
        if not referrer:
            return None, None
        if Referral.objects.filter(referred=student).exists():
            return None, None
        with transaction.atomic():
            Referral.objects.create(referrer=referrer, referred=student, points_earned=points)
            referrer.referral_points = (referrer.referral_points or 0) + points
            referrer.save(update_fields=['referral_points'])
        referred_name = f"{student.first_name} {student.last_name or ''}".strip()
        if not referred_name:
            referred_name = student.initial_full_name or student.username or "Yangi foydalanuvchi"
        return referrer.telegram_id, referred_name

    @staticmethod
    @sync_to_async
    def get_referral_leaderboard(limit: int = 10):
        """Get top students by referral_points. Excludes users without first_name.
        Tiebreaker: who reached their current points earlier (last referral date)."""
        return list(
            Student.objects.filter(is_active=True)
            .exclude(Q(first_name__isnull=True) | Q(first_name=''))
            .annotate(
                last_referral_at=Coalesce(
                    Max('referrals_made__created_at'),
                    F('created_at'),
                )
            )
            .order_by('-referral_points', 'last_referral_at')
            .values('telegram_id', 'first_name', 'last_name', 'referral_points')[:limit]
        )

    @staticmethod
    @sync_to_async
    def get_teachers_leaderboard(limit: int = 10):
        """Get top teachers by number of fully registered students, grouped by phone number."""
        # Using exact requirements for "fully registered"
        fully_registered_q = Q(student__registered_from_web=True) | (
            Q(student__first_name__gt='') &
            Q(student__last_name__isnull=False) & ~Q(student__last_name='') &
            Q(student__date_of_birth__isnull=False) &
            Q(student__document_number__isnull=False) & ~Q(student__document_number='') &
            Q(student__parent__isnull=False) & (~Q(student__parent__phone_number='') | ~Q(student__parent__phone_number2='')) &
            Q(student__teacher__isnull=False) & ~Q(student__teacher__phone_number='')
        )

        return list(
            Teacher.objects.filter(phone_number__isnull=False)
            .exclude(phone_number='')
            .filter(fully_registered_q)
            .values('phone_number')
            .annotate(
                student_count=Count('student'),
                full_name=Max('full_name')
            )
            .filter(student_count__gt=0)
            .order_by('-student_count', 'full_name')[:limit]
        )

    @staticmethod
    @sync_to_async
    def get_user_referral_rank(telegram_id: int):
        """Get current user's rank (1-based) by referral_points. Same order as leaderboard.
        Tiebreaker: who reached their current points earlier (last referral date)."""
        try:
            student = Student.objects.annotate(
                last_referral_at=Coalesce(Max('referrals_made__created_at'), F('created_at'))
            ).get(telegram_id=telegram_id, is_active=True)
        except Student.DoesNotExist:
            return None
        base = (
            Student.objects.filter(is_active=True)
            .exclude(Q(first_name__isnull=True) | Q(first_name=''))
            .annotate(
                last_referral_at=Coalesce(Max('referrals_made__created_at'), F('created_at'))
            )
        )
        above = base.filter(
            Q(referral_points__gt=student.referral_points)
            | Q(referral_points=student.referral_points, last_referral_at__lt=student.last_referral_at)
        ).count()
        return above + 1

    @staticmethod
    @sync_to_async
    def get_user_referral_rank_and_points(telegram_id: int):
        """
        Get current user's rank (1-based) and referral_points.
        Returns (rank, points) or (None, 0) if not found.
        Tiebreaker: who reached their current points earlier (last referral date).
        """
        try:
            student = Student.objects.annotate(
                last_referral_at=Coalesce(Max('referrals_made__created_at'), F('created_at'))
            ).get(telegram_id=telegram_id, is_active=True)
        except Student.DoesNotExist:
            return None, 0
        base = (
            Student.objects.filter(is_active=True)
            .exclude(Q(first_name__isnull=True) | Q(first_name=''))
            .annotate(
                last_referral_at=Coalesce(Max('referrals_made__created_at'), F('created_at'))
            )
        )
        above = base.filter(
            Q(referral_points__gt=student.referral_points)
            | Q(referral_points=student.referral_points, last_referral_at__lt=student.last_referral_at)
        ).count()
        points = student.referral_points or 0
        return above + 1, points


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
        """Set bot state for user. Also updates Student.state when state is a registration state."""
        with transaction.atomic():
            bot_state, _ = BotState.objects.update_or_create(
                telegram_id=telegram_id,
                defaults={
                    'state': state,
                    'state_data': state_data or {},
                    'updated_at': timezone.now(),
                }
            )
            # Keep Student.state in sync for registration flow (so it can be used for resume / admin)
            student_state = state if (state and state in REGISTRATION_STATE_NAMES) else None
            Student.objects.filter(telegram_id=telegram_id).update(state=student_state)
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
        """Clear bot state and Student.state for this user."""
        BotState.objects.filter(telegram_id=telegram_id).delete()
        Student.objects.filter(telegram_id=telegram_id).update(state=None)


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
    def get_active_tests_for_grade_and_language(grade: int, language: str = None):
        """Get all active tests for a grade, optionally filtered by language."""
        query = Test.objects.filter(grade=grade, is_active=True)
        if language:
            query = query.filter(language=language)
        return list(query.order_by('title'))

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
    def check_student_has_active_or_submitted_test(student, grade: int):
        """Check if student has any IN_PROGRESS or SUBMITTED_FINAL attempts for tests with this grade."""
        attempt = TestAttempt.objects.filter(
            student=student,
            test__grade=grade,
            status__in=['IN_PROGRESS', 'FINISHED_REVIEW', 'SUBMITTED_FINAL']
        ).select_related('test').first()
        return attempt
    
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
            attempt = TestAttempt.objects.select_related('test', 'student').get(id=attempt_id)
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
            attempt = TestAttempt.objects.select_related('test', 'student').get(id=attempt_id)
            attempt.status = 'FINISHED_REVIEW'
            attempt.save()
            return attempt
    
    @staticmethod
    @sync_to_async
    def submit_final(attempt_id: int):
        """Submit test attempt and calculate score."""
        with transaction.atomic():
            attempt = TestAttempt.objects.select_related('test', 'student').get(id=attempt_id)
            
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
            attempt = TestAttempt.objects.select_related('test', 'student').get(id=attempt_id)
            
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


class FeedbackService:
    """Service for feedback operations."""

    @staticmethod
    @sync_to_async
    def create_feedback(student: Student, feedback_type: str, text: str):
        """Create feedback."""
        with transaction.atomic():
            return Feedback.objects.create(
                student=student,
                type=feedback_type,
                text=text
            )


from admin_panel.models import BroadcastMessage
from admin_panel.registration_filters import filter_students_by_registration_steps

from aiogram.types import FSInputFile, InputMediaPhoto, InputMediaVideo
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError
from django.conf import settings
import os

# Telegram allows max 30 messages/second globally; we stay slightly under that.
_BROADCAST_RATE_LIMIT = 1 / 30  # seconds between sends


class BroadcastService:
    """Service for sending broadcast messages with optional media."""

    @staticmethod
    async def send_broadcast(broadcast_id: int, bot):
        """Send broadcast message (text / single media / media group) to filtered users."""
        try:
            broadcast = await sync_to_async(BroadcastMessage.objects.get)(id=broadcast_id)
        except BroadcastMessage.DoesNotExist:
            return

        broadcast.status = 'sending'
        broadcast.started_at = timezone.now()
        await sync_to_async(broadcast.save)()

        # Build filter query
        grade_filters = []
        if broadcast.target_grade_5: grade_filters.append(5)
        if broadcast.target_grade_6: grade_filters.append(6)
        if broadcast.target_grade_7: grade_filters.append(7)
        if broadcast.target_grade_8: grade_filters.append(8)
        target_not_fully_registered = getattr(broadcast, 'target_not_fully_registered', False)
        target_all_users = getattr(broadcast, 'target_all_users', False)

        def _get_broadcast_students():
            base = Student.objects.filter(is_active=True)
            target_registration_steps = getattr(broadcast, 'target_registration_steps', None) or []

            # If "broadcast to all users" is checked, return all active students
            if target_all_users:
                return list(base)

            if grade_filters:
                base = base.filter(grade__in=grade_filters)

            if target_registration_steps:
                base = filter_students_by_registration_steps(base, target_registration_steps)

            if not grade_filters and not target_registration_steps and not target_not_fully_registered:
                base = base.none()

            if target_not_fully_registered:
                from admin_panel.registration_filters import filter_students_by_registration_step
                admin_ids = list(getattr(settings, 'ADMIN_IDS', []))
                fully_registered = filter_students_by_registration_step(Student.objects.all(), 'fully_registered')
                base = base.exclude(
                    Q(pk__in=fully_registered.values_list('pk', flat=True)) | 
                    Q(telegram_id__in=admin_ids)
                )

            return list(base)

        def _get_media_files():
            return list(
                broadcast.media_files.order_by('order')
                .values_list('media_type', 'file', 'duration', 'width', 'height', 'thumbnail', named=False)
            )

        students = await sync_to_async(_get_broadcast_students)()
        print(f"Found {len(students)} students for broadcast. Telegram IDs: {students}")
        media_list = await sync_to_async(_get_media_files)()
        broadcast.recipient_count = len(students)
        await sync_to_async(broadcast.save)()

        sent_count = 0
        blocked_count = 0
        failed_count = 0
        error_messages = []

        # ── Step 1: Send the message to the first admin to get a stable message_id.
        # Then copy_message from that chat for every student — avoids re-uploading
        # files on disk and is much faster for large broadcasts.
        from_chat_id: int | None = None
        from_message_id: int | None = None

        if students:
            admin_ids = list(getattr(settings, 'ADMIN_IDS', []))
            if admin_ids:
                first_admin_id = admin_ids[0]
                # Build the first message for the admin (use the first student's name as preview)
                first_student = students[0]
                preview_name = (
                    first_student.first_name
                    or first_student.initial_full_name
                    or "O'quvchi"
                ).strip()
                preview_text = broadcast.message.format(
                    student_name=escape(preview_name),
                    user_name=escape(preview_name),
                )
                
                # Check for registration button for admin preview
                reply_markup = None
                if getattr(broadcast, 'include_register_button', False):
                    from bot.handlers.registration import _reg_webapp_url_with_user
                    from aiogram.types import WebAppInfo
                    url = _reg_webapp_url_with_user(first_admin_id, "")
                    if url:
                        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="📝 Ro'yxatdan o'tish", web_app=WebAppInfo(url=url))]
                        ])

                try:
                    sent_msg = await BroadcastService._send_raw(
                        bot, first_admin_id, preview_text, media_list, reply_markup=reply_markup
                    )
                    if sent_msg is not None:
                        from_chat_id = first_admin_id
                        from_message_id = sent_msg.message_id
                        sent_count += 1
                except Exception as e:
                    logger.warning("Could not send preview to admin %s: %s", first_admin_id, e)

        for student in students:
            async def _do_send(s=student):
                """Send to a single student — via copy_message if possible, else raw send."""
                display_name = (s.first_name or s.initial_full_name or "O'quvchi").strip()
                # Use escape to ensure any < or > in the user's name don't break HTML parsing
                safe_name = escape(display_name)
                
                # If there's no text (e.g. media without caption), don't format it
                if broadcast.message:
                    text = broadcast.message.format(
                        student_name=safe_name,
                        user_name=safe_name
                    )
                else:
                    text = ""

                reply_markup = None
                if getattr(broadcast, 'include_register_button', False):
                    from bot.handlers.registration import _reg_webapp_url_with_user
                    from aiogram.types import WebAppInfo
                    url = _reg_webapp_url_with_user(s.telegram_id, s.phone_number or "")
                    if url:
                        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="📝 Ro'yxatdan o'tish", web_app=WebAppInfo(url=url))]
                        ])

                if from_chat_id and from_message_id:
                    if not media_list:
                        # For text-only messages, copy_message copies the exact text.
                        # We cannot customize {student_name} per user if we copy a text message,
                        # because copy_message ignores the 'caption' parameter for text messages.
                        # Therefore, we MUST use send_message to allow personalizing the text.
                        await bot.send_message(
                            chat_id=s.telegram_id,
                            text=text,
                            parse_mode=ParseMode.HTML,
                            reply_markup=reply_markup,
                        )
                    else:
                        # For media messages, copy_message replaces the caption with our new personalized caption.
                        await bot.copy_message(
                            chat_id=s.telegram_id,
                            from_chat_id=from_chat_id,
                            message_id=from_message_id,
                            caption=text,
                            parse_mode=ParseMode.HTML,
                            reply_markup=reply_markup,
                        )
                else:
                    await BroadcastService._send_raw(bot, s.telegram_id, text, media_list, reply_markup=reply_markup)

            try:
                try:
                    await _do_send(student)
                except TelegramRetryAfter as e:
                    # Telegram is rate-limiting us — wait the required time, then retry once
                    logger.warning(
                        "Broadcast rate-limited by Telegram (retry_after=%ss), waiting…",
                        e.retry_after,
                    )
                    await asyncio.sleep(e.retry_after)
                    await _do_send(student)  # one retry after waiting
                sent_count += 1

            except TelegramForbiddenError:
                # User blocked the bot or deactivated their account
                blocked_count += 1

            except Exception as e:
                failed_count += 1
                if len(error_messages) < 50:
                    error_messages.append(f"Student {student.telegram_id}: {str(e)}")

            # Enforce Telegram's global limit: max 30 messages/second
            await asyncio.sleep(_BROADCAST_RATE_LIMIT)

            # Periodically save progress to DB every 50 students
            if (sent_count + blocked_count + failed_count) % 50 == 0:
                broadcast.sent_count = sent_count
                broadcast.blocked_count = blocked_count
                broadcast.failed_count = failed_count
                if error_messages:
                    broadcast.error_log = "\n".join(error_messages)
                await sync_to_async(broadcast.save)()


        broadcast.status = 'completed'
        broadcast.completed_at = timezone.now()
        broadcast.sent_count = sent_count
        broadcast.blocked_count = blocked_count
        broadcast.failed_count = failed_count
        if error_messages:
            broadcast.error_log = "\n".join(error_messages)
        await sync_to_async(broadcast.save)()

    @staticmethod
    async def _send_raw(bot, chat_id: int, text: str, media_list: list, reply_markup=None):
        """Send a message/media directly (without copy_message). Returns the sent Message object."""
        clean_text = text if text else None
        
        if len(media_list) == 0:
            if not clean_text:
                return None  # Cannot send a text message without text
            return await bot.send_message(
                chat_id=chat_id,
                text=clean_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
        elif len(media_list) == 1:
            media_type, file_name, duration, width, height, thumb = media_list[0]
            file_path = os.path.join(settings.MEDIA_ROOT, file_name)
            fs_input = FSInputFile(file_path)
            if media_type == 'video':
                video_kwargs = {
                    'chat_id': chat_id,
                    'video': fs_input,
                    'caption': clean_text,
                    'parse_mode': ParseMode.HTML if clean_text else None,
                    'supports_streaming': True,
                    'reply_markup': reply_markup,
                }
                if duration:
                    video_kwargs['duration'] = duration
                if width:
                    video_kwargs['width'] = width
                if height:
                    video_kwargs['height'] = height
                if thumb:
                    thumb_path = os.path.join(settings.MEDIA_ROOT, thumb)
                    if os.path.isfile(thumb_path):
                        video_kwargs['thumbnail'] = FSInputFile(thumb_path)
                return await bot.send_video(**video_kwargs)
            else:
                return await bot.send_photo(
                    chat_id=chat_id,
                    photo=fs_input,
                    caption=clean_text,
                    parse_mode=ParseMode.HTML if clean_text else None,
                    reply_markup=reply_markup,
                )
        else:
            group = []
            for idx, (media_type, file_name, duration, width, height, thumb) in enumerate(media_list):
                file_path = os.path.join(settings.MEDIA_ROOT, file_name)
                fs_input = FSInputFile(file_path)
                caption_kwargs = {}
                if idx == 0 and clean_text:
                    caption_kwargs = {'caption': clean_text, 'parse_mode': ParseMode.HTML}
                if media_type == 'video':
                    vid_extra = {}
                    if duration:
                        vid_extra['duration'] = duration
                    if width:
                        vid_extra['width'] = width
                    if height:
                        vid_extra['height'] = height
                    if thumb:
                        thumb_path = os.path.join(settings.MEDIA_ROOT, thumb)
                        if os.path.isfile(thumb_path):
                            vid_extra['thumbnail'] = FSInputFile(thumb_path)
                    group.append(InputMediaVideo(
                        media=fs_input, supports_streaming=True,
                        **caption_kwargs, **vid_extra,
                    ))
                else:
                    group.append(InputMediaPhoto(media=fs_input, **caption_kwargs))
            msgs = await bot.send_media_group(chat_id=chat_id, media=group)
            if reply_markup and msgs:
                # Media group doesn't support reply_markup, so we send it as a separate follow-up message if needed
                await bot.send_message(
                    chat_id=chat_id, 
                    text="Ro'yxatdan o'tish uchun tugmani bosing:", 
                    reply_markup=reply_markup
                )
            return msgs[0] if msgs else None


def build_channel_keyboard(missing_channels) -> InlineKeyboardMarkup:
    """Build inline keyboard listing mandatory channels the user hasn't joined yet,
    plus a 'check subscription' button. Used by both registration flow and middleware."""
    keyboard = []
    for ch in missing_channels:
        link = ch.channel_username
        if not link and ch.channel_id.startswith('@'):
            link = f"https://t.me/{ch.channel_id[1:]}"
        if not link:
            link = "https://t.me/"
        keyboard.append([InlineKeyboardButton(text=f"📢 {ch.title}", url=link)])
    keyboard.append([InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_subs")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
