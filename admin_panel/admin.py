"""Django admin configuration with django-unfold."""
import time
import logging
from django.contrib import admin
from django.contrib import messages
from django.db.models import Q, Max, F, FloatField, OuterRef, Subquery
from django.db.models.functions import Coalesce
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display

from .models import (
    Student,
    Parent,
    Teacher,
    Certificate,
    Test,
    TestQuestion,
    TestAttempt,
    TestAnswer,
)
from .utils import send_test_assignment_message, send_certificate_message
from .certificate_generator import generate_certificate

logger = logging.getLogger(__name__)


class LastTestAttemptScoreFilter(admin.SimpleListFilter):
    """Filter students by their last TestAttempt score."""
    title = "Oxirgi test balli"
    parameter_name = 'last_test_score'

    def lookups(self, request, model_admin):
        return (
            ('0-50', '0-50%'),
            ('50-70', '50-70%'),
            ('70-85', '70-85%'),
            ('85-100', '85-100%'),
            ('100', '100%'),
        )

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        
        # Get the score range
        if self.value() == '0-50':
            min_score, max_score = 0, 50
        elif self.value() == '50-70':
            min_score, max_score = 50, 70
        elif self.value() == '70-85':
            min_score, max_score = 70, 85
        elif self.value() == '85-100':
            min_score, max_score = 85, 100
        elif self.value() == '100':
            min_score, max_score = 100, 100
        else:
            return queryset
        
        # Get students with last test attempt scores in the range
        # We'll filter by getting the latest TestAttempt for each student
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


@admin.register(Student)
class StudentAdmin(ModelAdmin):
    """Admin for Student model."""
    list_display = ['telegram_id', 'first_name', 'last_name', 'grade', 'last_test_score_display', 'school_name', 'is_active', 'created_at']
    list_filter = ['grade', 'is_active', LastTestAttemptScoreFilter, 'created_at']
    search_fields = ['telegram_id', 'first_name', 'last_name', 'username', 'phone_number', 'school_name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    actions = ['send_certificate_action']
    
    def get_queryset(self, request):
        """Annotate queryset with last test attempt score."""
        qs = super().get_queryset(request)
        # Get the last test attempt score for each student
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


class TestQuestionInline(TabularInline):
    """Inline admin for TestQuestion."""
    model = TestQuestion
    extra = 1
    fields = [
        'question_number',
        'type',
        'text',
        'image_file_id',
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
                logger.error("Failed to send test to %s: %s", student.telegram_id, e)
                if attempt:
                    attempt.delete()

        self.message_user(
            request,
            f"Yuborildi: {sent_count} | O'tkazib yuborildi: {skip_count} (oldin yuborilgan)",
            level=messages.SUCCESS
        )
    send_test_to_students_action.short_description = "Testni o'quvchilarga yuborish"


@admin.register(TestQuestion)
class TestQuestionAdmin(ModelAdmin):
    """Admin for TestQuestion model."""
    list_display = [
        'test',
        'question_number',
        'type',
        'text_short',
        'correct_answer',
        'ball_weight',
        'created_at'
    ]
    list_filter = ['test', 'type', 'created_at']
    search_fields = ['text', 'option_a', 'option_b', 'option_c', 'option_d']
    readonly_fields = ['created_at']
    ordering = ['test', 'question_number']
    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('test', 'question_number', 'type', 'text', 'image_file_id')
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
