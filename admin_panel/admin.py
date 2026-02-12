"""Django admin configuration with django-unfold."""
import csv
import io
import time
import logging
from django import forms
from django.contrib import admin
from django.contrib import messages
from django.db.models import Q, Max, F, FloatField, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from unfold.admin import ModelAdmin, StackedInline, TabularInline
from unfold.decorators import display

from .models import (
    Student,
    StudentRating,
    Parent,
    Teacher,
    Certificate,
    Test,
    TestQuestion,
    TestAttempt,
    TestAnswer,
    Referral,
    MandatoryChannel,
    Feedback,
    BroadcastMessage,
)
from .utils import send_test_assignment_message, send_certificate_message
from .certificate_generator import generate_certificate

logger = logging.getLogger(__name__)


# Unused - kept so any stray reference (e.g. cached template/import) does not raise NameError
class MinTestScoreFilterForm(forms.Form):
    min_test_score = forms.IntegerField(required=False, min_value=0, max_value=100)


class LastTestAttemptScoreFilter(admin.SimpleListFilter):
    """Filter students by their last TestAttempt score."""
    title = "Oxirgi test balli"
    parameter_name = 'last_test_score'

    def lookups(self, request, model_admin):
        return (
            ('80-100', '80+'),
            ('90-100', '90+'),
            ('100', '100'),
        )

    def queryset(self, request, queryset):
        if not self.value():
            return queryset

        if self.value() == '80-100':
            min_score, max_score = 80, 100
        elif self.value() == '90-100':
            min_score, max_score = 90, 100
        elif self.value() == '100':
            min_score, max_score = 100, 100
        else:
            return queryset

        student_ids = []
        for student in queryset:
            last_attempt = TestAttempt.objects.filter(
                student=student,
                score__isnull=False
            ).order_by('-submitted_at', '-created_at').first()

            if last_attempt and last_attempt.score is not None:
                if min_score <= last_attempt.score <= max_score:
                    student_ids.append(student.pk)

        return queryset.filter(pk__in=student_ids)


class FullyRegisteredFilter(admin.SimpleListFilter):
    """Filter students by full registration: core fields + parent and teacher with phone numbers."""
    title = "To'liq ro'yxatdan o'tgan"
    parameter_name = 'fully_registered'

    def lookups(self, request, model_admin):
        return (
            ('yes', "Ha"),
            ('no', "Yo'q"),
        )

    def queryset(self, request, queryset):
        # Core student fields
        base = queryset.filter(
            Q(first_name__gt=''),
            Q(last_name__isnull=False) & ~Q(last_name=''),
            date_of_birth__isnull=False,
            document_number__isnull=False,
            document_number__gt='',
        )
        # Parent exists and has at least one phone
        with_parent_phone = base.filter(
            parent__isnull=False,
        ).filter(
            Q(parent__phone_number__gt='') | Q(parent__phone_number2__gt=''),
        )
        # Teacher exists and has phone
        fully_registered = with_parent_phone.filter(
            teacher__isnull=False,
            teacher__phone_number__gt='',
        )
        if self.value() == 'yes':
            return fully_registered
        if self.value() == 'no':
            return queryset.exclude(pk__in=fully_registered.values_list('pk', flat=True))
        return queryset


class RegistrationStepFilter(admin.SimpleListFilter):
    """Filter students by registration step (where they stopped in the flow)."""
    title = "Ro'yxatdan o'tish bosqichi"
    parameter_name = 'reg_step'

    def lookups(self, request, model_admin):
        return (
            ('not_started', "Boshlanmagan"),
            ('stage1_only', "1-bosqich (ism-fon)"),
            ('first_name', "Ism"),
            ('last_name', "Familiya"),
            ('date_of_birth', "Tug'ilgan sana"),
            ('document_number', "Metrika"),
            ('region', "Viloyat"),
            ('district', "Tuman/shahar"),
            ('school_name', "Maktab"),
            ('grade', "Sinf (5-8)"),
            ('photo', "Foto"),
            ('guardian', "Vasiy (telefon bilan)"),
            ('teacher', "Ustoz (telefon bilan)"),
            ('source', "Manba"),
            ('fully_registered', "To'liq ro'yxatdan o'tgan"),
        )

    def queryset(self, request, queryset):
        v = self.value()
        if not v:
            return queryset

        if v == 'not_started':
            return queryset.filter(Q(initial_full_name__isnull=True) | Q(initial_full_name=''))

        if v == 'stage1_only':
            return queryset.filter(initial_full_name__gt='').filter(
                Q(first_name__isnull=True) | Q(first_name='')
            )

        if v == 'first_name':
            return queryset.filter(first_name__gt='').filter(
                Q(last_name__isnull=True) | Q(last_name='')
            )

        if v == 'last_name':
            return queryset.filter(first_name__gt='').filter(
                Q(last_name__isnull=False) & ~Q(last_name='')
            ).filter(date_of_birth__isnull=True)

        if v == 'date_of_birth':
            return queryset.filter(date_of_birth__isnull=False).filter(
                Q(document_number__isnull=True) | Q(document_number='')
            )

        if v == 'document_number':
            return queryset.filter(document_number__isnull=False).filter(
                document_number__gt=''
            ).filter(Q(region__isnull=True) | Q(region=''))

        if v == 'region':
            return queryset.filter(region__isnull=False).filter(
                Q(district__isnull=True) | Q(district='')
            )

        if v == 'district':
            return queryset.filter(district__isnull=False).filter(
                Q(school_name__isnull=True) | Q(school_name='')
            )

        if v == 'school_name':
            return queryset.filter(school_name__isnull=False).filter(
                school_name__gt=''
            ).filter(grade__isnull=True)

        if v == 'grade':
            return queryset.filter(grade__in=[5, 6, 7, 8]).filter(
                Q(photo__isnull=True) | Q(photo='')
            )

        if v == 'photo':
            has_grade_or_other = Q(grade__in=[5, 6, 7, 8]) | (
                Q(school_name__gt='') & Q(grade__isnull=True)
            )
            return queryset.filter(has_grade_or_other).filter(
                Q(photo__isnull=True) | Q(photo='')
            )

        if v == 'guardian':
            has_photo = Q(photo__isnull=False) & ~Q(photo='')
            has_grade_or_other = Q(grade__in=[5, 6, 7, 8]) | (
                Q(school_name__gt='') & Q(grade__isnull=True)
            )
            with_photo = queryset.filter(has_grade_or_other).filter(has_photo)
            with_parent = with_photo.filter(parent__isnull=False).filter(
                Q(parent__phone_number__gt='') | Q(parent__phone_number2__gt='')
            )
            return with_photo.exclude(pk__in=with_parent.values_list('pk', flat=True))

        if v == 'teacher':
            with_parent = queryset.filter(parent__isnull=False).filter(
                Q(parent__phone_number__gt='') | Q(parent__phone_number2__gt='')
            )
            with_teacher = with_parent.filter(teacher__isnull=False).filter(
                teacher__phone_number__gt=''
            )
            return with_parent.exclude(pk__in=with_teacher.values_list('pk', flat=True))

        if v == 'source':
            with_teacher = queryset.filter(teacher__isnull=False).filter(
                teacher__phone_number__gt=''
            ).filter(parent__isnull=False).filter(
                Q(parent__phone_number__gt='') | Q(parent__phone_number2__gt='')
            )
            fully = with_teacher.filter(
                Q(first_name__gt=''),
                Q(last_name__isnull=False) & ~Q(last_name=''),
                date_of_birth__isnull=False,
                document_number__isnull=False,
                document_number__gt='',
            )
            return with_teacher.exclude(pk__in=fully.values_list('pk', flat=True))

        if v == 'fully_registered':
            base = queryset.filter(
                Q(first_name__gt=''),
                Q(last_name__isnull=False) & ~Q(last_name=''),
                date_of_birth__isnull=False,
                document_number__isnull=False,
                document_number__gt='',
            )
            return base.filter(parent__isnull=False).filter(
                Q(parent__phone_number__gt='') | Q(parent__phone_number2__gt='')
            ).filter(teacher__isnull=False, teacher__phone_number__gt='')

        return queryset


@admin.register(Student)
class StudentAdmin(ModelAdmin):
    """Admin for Student model."""
    list_display = ['telegram_id', 'first_name', 'last_name', 'grade', 'is_fully_registered_display', 'last_test_score_display', 'referral_points', 'school_name', 'is_active', 'created_at']
    list_filter = ['grade', 'is_active', RegistrationStepFilter, FullyRegisteredFilter, LastTestAttemptScoreFilter, 'created_at']
    search_fields = ['telegram_id', 'first_name', 'last_name', 'username', 'phone_number', 'school_name', 'referral_code']
    readonly_fields = ['created_at', 'updated_at', 'referral_points', 'referral_code']
    ordering = ['-created_at']
    actions = ['send_certificate_action', 'export_students_csv']

    def get_queryset(self, request):
        """Annotate queryset with last test attempt score."""
        qs = super().get_queryset(request)
        last_attempt_subquery = TestAttempt.objects.filter(
            student=OuterRef('pk'),
            score__isnull=False
        ).order_by('-submitted_at', '-created_at').values('score')[:1]
        return qs.annotate(
            last_test_score=Coalesce(
                Subquery(last_attempt_subquery),
                None,
                output_field=FloatField()
            )
        )
    
    @display(description="To'liq ro'yxatdan o'tgan")
    def is_fully_registered_display(self, obj):
        """Display whether student completed Stage 2 registration."""
        return "Ha" if obj.is_fully_registered else "Yo'q"

    @display(description='Oxirgi test balli')
    def last_test_score_display(self, obj):
        """Display last test attempt score."""
        if hasattr(obj, 'last_test_score') and obj.last_test_score is not None:
            return f"{obj.last_test_score:.1f}%"
        return "-"
    
    def send_certificate_action(self, request, queryset):
        """Generate and send certificates to selected students based on their last TestAttempt."""
        import time
        
        sent_count = 0
        error_count = 0
        skipped_count = 0
        
        for student in queryset:
            # Get the last completed TestAttempt for this student
            last_attempt = TestAttempt.objects.filter(
                student=student,
                score__isnull=False,
                status__in=['SUBMITTED_FINAL', 'FINISHED_REVIEW']
            ).order_by('-submitted_at', '-created_at').first()
            
            if not last_attempt:
                skipped_count += 1
                logger.warning("No completed test attempt found for student %s (ID: %s)", 
                             student.first_name, student.telegram_id)
                continue
            
            try:
                # Generate certificate
                certificate_path, certificate_number = generate_certificate(student, last_attempt)
                
                # Send certificate with delay (1 second between messages)
                send_certificate_message(
                    student.telegram_id,
                    certificate_path,
                    delay_seconds=1.0
                )
                
                sent_count += 1
                logger.info("Certificate sent to student %s (ID: %s)", 
                          student.first_name, student.telegram_id)
                
                # Wait between messages to avoid rate limiting
                time.sleep(1.0)
                
            except Exception as e:
                error_count += 1
                logger.error("Failed to send certificate to student %s (ID: %s): %s", 
                           student.first_name, student.telegram_id, e)
        
        self.message_user(
            request,
            f"Sertifikatlar yuborildi: {sent_count} | Xatolar: {error_count} | O'tkazib yuborildi: {skipped_count} (test topshirilmagan)",
            level=messages.SUCCESS if error_count == 0 else messages.WARNING
        )
    
    send_certificate_action.short_description = "Sertifikat yuborish (oxirgi test bo'yicha)"

    def export_students_csv(self, request, queryset):
        """Export selected students to CSV."""
        if not queryset.exists():
            self.message_user(request, "Eksport qilish uchun kamida bitta o'quvchini tanlang.", level=messages.WARNING)
            return

        # Re-annotate with last_test_score for export
        last_attempt_subquery = TestAttempt.objects.filter(
            student=OuterRef('pk'),
            score__isnull=False
        ).order_by('-submitted_at', '-created_at').values('score')[:1]
        qs = queryset.annotate(
            last_test_score=Coalesce(
                Subquery(last_attempt_subquery),
                None,
                output_field=FloatField()
            )
        ).order_by('-created_at')

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        # Header row
        headers = [
            'telegram_id', 'username', 'first_name', 'last_name', 'middle_name',
            'grade', 'last_test_score', 'referral_points', 'school_name', 'region', 'district',
            'phone_number', 'document_number', 'date_of_birth', 'language',
            'initial_full_name', 'phone_owner', 'achievements_description',
            'referral_code', 'is_active', 'created_at', 'updated_at',
        ]
        writer.writerow(headers)

        for obj in qs:
            last_score = getattr(obj, 'last_test_score', None)
            last_score_str = f"{last_score:.1f}" if last_score is not None else ""
            row = [
                obj.telegram_id,
                obj.username or "",
                obj.first_name or "",
                obj.last_name or "",
                obj.middle_name or "",
                obj.grade if obj.grade is not None else "",
                last_score_str,
                obj.referral_points or 0,
                obj.school_name or "",
                obj.region or "",
                obj.district or "",
                obj.phone_number or "",
                obj.document_number or "",
                obj.date_of_birth.isoformat() if obj.date_of_birth else "",
                obj.language or "",
                obj.initial_full_name or "",
                obj.phone_owner or "",
                (obj.achievements_description or "")[:500],
                obj.referral_code or "",
                obj.is_active,
                obj.created_at.strftime("%Y-%m-%d %H:%M") if obj.created_at else "",
                obj.updated_at.strftime("%Y-%m-%d %H:%M") if obj.updated_at else "",
            ]
            writer.writerow(row)

        response = HttpResponse(
            buffer.getvalue().encode('utf-8-sig'),
            content_type='text/csv; charset=utf-8-sig'
        )
        response['Content-Disposition'] = 'attachment; filename="students.csv"'
        return response

    export_students_csv.short_description = "Tanlanganlarni CSV ga eksport qilish"


@admin.register(StudentRating)
class StudentRatingAdmin(ModelAdmin):
    """Admin for referral leaderboard: list only, no add/change/delete/view."""
    list_display = ['rank', 'first_name', 'last_name', 'telegram_id', 'referral_points']
    list_display_links = []  # no link to detail view
    ordering = ['-referral_points', '-created_at']
    search_fields = ['first_name', 'last_name', 'telegram_id']
    list_per_page = 50

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_active=True)

    @display(description='#')
    def rank(self, obj):
        """1-based order number by referral_points, then created_at."""
        if obj is None:
            return ''
        above = StudentRating.objects.filter(is_active=True).filter(
            Q(referral_points__gt=obj.referral_points)
            | Q(referral_points=obj.referral_points, created_at__lt=obj.created_at)
        ).count()
        return above + 1

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False



@admin.register(Referral)
class ReferralAdmin(ModelAdmin):
    """Admin for Referral model. Read-only: referrals are created by bot on signup."""
    list_display = ['referrer', 'referred', 'points_earned', 'created_at']
    list_filter = ['created_at']
    search_fields = ['referrer__first_name', 'referrer__last_name', 'referred__first_name', 'referred__last_name']
    readonly_fields = ['referrer', 'referred', 'points_earned', 'created_at']
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Parent)
class ParentAdmin(ModelAdmin):
    """Admin for Parent model."""
    list_display = ['full_name', 'student', 'phone_number', 'relationship', 'created_at']
    search_fields = ['full_name', 'phone_number', 'student__first_name', 'student__last_name']
    readonly_fields = ['created_at']


@admin.register(Teacher)
class TeacherAdmin(ModelAdmin):
    """Admin for Teacher model."""
    list_display = ['full_name', 'student', 'phone_number', 'created_at']
    search_fields = ['full_name', 'phone_number', 'student__first_name', 'student__last_name']
    readonly_fields = ['created_at']


@admin.register(Certificate)
class CertificateAdmin(ModelAdmin):
    """Admin for Certificate model."""
    list_display = ['certificate_number', 'student', 'exam', 'generated_at']
    list_filter = ['generated_at', 'exam']
    search_fields = ['certificate_number', 'student__first_name', 'student__last_name', 'exam__title']
    readonly_fields = ['generated_at']
    ordering = ['-generated_at']


class TestQuestionInline(StackedInline):
    """Inline admin for TestQuestion."""
    model = TestQuestion
    extra = 1
    fields = [
        'question_number',
        'text',
        'image',
        'option_a',
        'option_b',
        'option_c',
        'option_d',
        'correct_answer',
        'ball_weight',
    ]
    ordering = ['question_number']


@admin.register(Test)
class TestAdmin(ModelAdmin):
    """Admin for Test model."""
    list_display = ['title', 'grade', 'language', 'version', 'duration_minutes', 'questions_count', 'is_active', 'created_at']
    list_filter = ['grade', 'language', 'is_active', 'created_at']
    search_fields = ['title', 'version']
    readonly_fields = ['created_at', 'updated_at', 'questions_count']
    ordering = ['grade', 'title', 'version']
    inlines = [TestQuestionInline]
    actions = ['send_test_to_students_action']
    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('title', 'grade', 'language', 'version', 'duration_minutes', 'is_active')
        }),
        ('Statistika', {
            'fields': ('questions_count',),
            'classes': ('collapse',)
        }),
        ('Vaqt', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @display(description='Savollar soni')
    def questions_count(self, obj):
        """Return the number of questions."""
        return obj.get_questions_count()

    def send_test_to_students_action(self, request, queryset):
        """Assign test to students (create PENDING attempt) and send Telegram notification."""
        if queryset.count() != 1:
            self.message_user(
                request,
                "Iltimos, faqat bitta testni tanlang.",
                level=messages.ERROR
            )
            return

        test = queryset.first()

        if test.get_questions_count() == 0:
            self.message_user(
                request,
                "Testda savollar yo'q. Avval savollar qo'shing, keyin yuboring.",
                level=messages.ERROR
            )
            return

        query = Q(grade=test.grade, is_active=True)
        if test.language:
            query &= Q(language=test.language)

        students = Student.objects.filter(query)
        sent_count = 0
        skip_count = 0
        error_count = 0

        for student in students:
            attempt_exists = TestAttempt.objects.filter(
                test=test,
                student=student,
                status__in=['PENDING', 'IN_PROGRESS', 'FINISHED_REVIEW'],
            ).exists()

            if attempt_exists:
                skip_count += 1
                continue

            attempt = None
            try:
                attempt = TestAttempt.objects.create(
                    student=student,
                    test=test,
                    status='PENDING',
                    started_at=None,
                    expires_at=None,
                )
                send_test_assignment_message(student.telegram_id, test, with_start_button=True)
                sent_count += 1
                
                # Wait 1 second between messages to avoid rate limiting
                time.sleep(1.0)
            except Exception as e:
                error_count += 1
                logger.error("Failed to send test to student %s (ID: %s): %s", 
                           student.first_name, student.telegram_id, e, exc_info=True)
                if attempt:
                    attempt.delete()

        message = f"Yuborildi: {sent_count} | O'tkazib yuborildi: {skip_count} (oldin yuborilgan)"
        if error_count > 0:
            message += f" | Xatolar: {error_count}"
        
        self.message_user(
            request,
            message,
            level=messages.SUCCESS if error_count == 0 else messages.WARNING
        )
    send_test_to_students_action.short_description = "Testni o'quvchilarga yuborish"


@admin.register(TestQuestion)
class TestQuestionAdmin(ModelAdmin):
    """Admin for TestQuestion model."""
    list_display = [
        'test',
        'question_number',
        'text_short',
        'correct_answer',
        'ball_weight',
        'created_at'
    ]
    list_filter = ['test', 'created_at']
    search_fields = ['text', 'option_a', 'option_b', 'option_c', 'option_d']
    readonly_fields = ['created_at']
    ordering = ['test', 'question_number']
    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('test', 'question_number', 'text', 'image'),
        }),
        ('Variantlar', {
            'fields': ('option_a', 'option_b', 'option_c', 'option_d')
        }),
        ('Javob', {
            'fields': ('correct_answer', 'ball_weight')
        }),
        ('Vaqt', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    @display(description='Savol')
    def text_short(self, obj):
        """Return shortened question text."""
        return obj.text[:100] + '...' if len(obj.text) > 100 else obj.text


class TestAnswerInline(TabularInline):
    """Inline admin for TestAnswer."""
    model = TestAnswer
    extra = 0
    fields = [
        'question',
        'answer_choice',
        'is_correct',
        'points_earned',
        'answered_at',
    ]
    readonly_fields = ['answered_at']
    ordering = ['question__question_number']


@admin.register(TestAttempt)
class TestAttemptAdmin(ModelAdmin):
    """Admin for TestAttempt model."""
    list_display = [
        'student',
        'test',
        'status',
        'score',
        'earned_points',
        'total_points',
        'started_at',
        'submitted_at',
    ]
    list_filter = ['status', 'test', 'created_at']
    search_fields = [
        'student__first_name',
        'student__last_name',
        'student__telegram_id',
        'test__title',
    ]
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    inlines = [TestAnswerInline]
    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('student', 'test', 'status')
        }),
        ('Balllar', {
            'fields': ('score', 'earned_points', 'total_points')
        }),
        ('Vaqt', {
            'fields': ('started_at', 'submitted_at', 'expires_at', 'created_at', 'updated_at')
        }),
    )

    @display(description='Ball %')
    def score(self, obj):
        return f"{obj.score}%" if obj.score else "-"


@admin.register(TestAnswer)
class TestAnswerAdmin(ModelAdmin):
    """Admin for TestAnswer model."""
    list_display = [
        'attempt',
        'question',
        'answer_choice',
        'is_correct',
        'points_earned',
        'answered_at',
    ]
    list_filter = ['is_correct', 'answered_at']
    search_fields = [
        'attempt__student__first_name',
        'question__text',
    ]
    readonly_fields = ['answered_at', 'updated_at']
    ordering = ['-answered_at']


@admin.register(MandatoryChannel)
class MandatoryChannelAdmin(ModelAdmin):
    """Admin for MandatoryChannel model."""
    list_display = ['title', 'channel_id', 'channel_username', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'channel_id', 'channel_username']
    readonly_fields = ['created_at']


@admin.register(Feedback)
class FeedbackAdmin(ModelAdmin):
    """Admin for Feedback model."""
    list_display = ['student', 'type', 'text_short', 'created_at']
    list_filter = ['type', 'created_at']
    search_fields = ['student__first_name', 'student__last_name', 'text']
    readonly_fields = ['created_at']


    @display(description='Matn')
    def text_short(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text


from asgiref.sync import async_to_sync
from bot.services import BroadcastService

# Actually, getting bot instance in django admin context might be tricky if not running alongside.
# But for now, let's assume we can initialize it or import it.
# Check where bot is initialized. It seems to be in a management command usually.
# However, for admin actions, we might need to initialize a fresh Bot instance with the token.
from aiogram import Bot
from django.conf import settings

@admin.register(BroadcastMessage)
class BroadcastMessageAdmin(ModelAdmin):
    """Admin for BroadcastMessage."""
    list_display = ['created_at', 'status', 'recipient_count', 'sent_count', 'blocked_count', 'failed_count']
    list_filter = ['status', 'created_at']
    readonly_fields = [
        'status', 'recipient_count', 'sent_count', 'blocked_count', 
        'failed_count', 'started_at', 'completed_at', 'created_at'
    ]
    actions = ['send_broadcast_action']

    def get_readonly_fields(self, request, obj=None):
        """Make fields readonly if not draft."""
        if obj and obj.status != 'draft':
            return [f.name for f in self.model._meta.fields]
        return self.readonly_fields

    def send_broadcast_action(self, request, queryset):
        """Send filtered messages."""
        count = 0
        for broadcast in queryset:
            if broadcast.status != 'draft':
                self.message_user(request, f"Xabarnoma {broadcast.id} oxiriga yetkazilmagan (Holat: {broadcast.status})", level=messages.WARNING)
                continue
            
            # Initialize bot
            # Note: Initializing bot inside a sync view
            bot = Bot(token=settings.BOT_TOKEN)
            
            try:
                # Run async service synchronously
                async_to_sync(BroadcastService.send_broadcast)(broadcast.id, bot)
                count += 1
                
                # Close session if needed (Aiogram 3 bot session handling)
                async_to_sync(bot.session.close)()
                
            except Exception as e:
                logger.error(f"Error sending broadcast {broadcast.id}: {e}")
                self.message_user(request, f"Xatolik: {e}", level=messages.ERROR)

        self.message_user(request, f"{count} ta xabarnoma yuborildi.", level=messages.SUCCESS)
    
    send_broadcast_action.short_description = "Xabarnomani yuborish"

