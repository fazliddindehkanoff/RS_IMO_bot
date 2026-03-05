"""Django admin configuration with django-unfold."""
import csv
import io
import time
import logging
import threading
from django import forms
from django.contrib import admin
from django.contrib import messages
from django.db.models import Q, Max, F, FloatField, OuterRef, Subquery, Window, Count
from django.db.models.functions import Coalesce, RowNumber
from django.http import HttpResponse
from django.utils import timezone
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
    BroadcastMedia,
    RegistrationSource,
    Partner,
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
            return queryset.filter(last_test_score__gte=80, last_test_score__lte=100)
        elif self.value() == '90-100':
            return queryset.filter(last_test_score__gte=90, last_test_score__lte=100)
        elif self.value() == '100':
            return queryset.filter(last_test_score=100)
        return queryset


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
            ('initial_full_name', "Ism-familiya (1-bosqich)"),
            ('initial_phone', "Telefon (1-bosqich)"),
            ('phone_owner', "Telefon egasi (1-bosqich)"),
            ('stage1_only', "1-bosqich tugallangan (olimpiada boshlanmagan)"),
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

        if v == 'initial_full_name':
            return queryset.filter(initial_full_name__gt='').filter(
                Q(phone_number__isnull=True) | Q(phone_number='')
            )

        if v == 'initial_phone':
            return queryset.filter(initial_full_name__gt='').filter(
                Q(phone_number__isnull=False) & ~Q(phone_number='')
            ).filter(Q(phone_owner__isnull=True) | Q(phone_owner=''))

        if v == 'phone_owner':
            return queryset.filter(initial_full_name__gt='').filter(
                Q(phone_number__isnull=False) & ~Q(phone_number='')
            ).filter(Q(phone_owner__isnull=False) & ~Q(phone_owner='')).filter(
                Q(first_name__isnull=True) | Q(first_name='')
            )

        if v == 'stage1_only':
            return queryset.filter(initial_full_name__gt='').filter(
                Q(phone_number__isnull=False) & ~Q(phone_number='')
            ).filter(Q(phone_owner__isnull=False) & ~Q(phone_owner='')).filter(
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
            # Has everything up to and including teacher, but no RegistrationSource yet
            has_all_before_source = queryset.filter(
                Q(first_name__gt=''),
                Q(last_name__isnull=False) & ~Q(last_name=''),
                date_of_birth__isnull=False,
                document_number__isnull=False,
                document_number__gt='',
            ).filter(parent__isnull=False).filter(
                Q(parent__phone_number__gt='') | Q(parent__phone_number2__gt='')
            ).filter(teacher__isnull=False, teacher__phone_number__gt='')
            return has_all_before_source.filter(registration_source__isnull=True)

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


class RegistrationSourceFilter(admin.SimpleListFilter):
    """Filter students by registration source (how they found us)."""
    title = "Manba"
    parameter_name = 'registration_source'

    def lookups(self, request, model_admin):
        return (('none', "Manba yo'q"),) + tuple(
            (choice[0], choice[1]) for choice in RegistrationSource.SOURCE_TYPE_CHOICES
        )

    def queryset(self, request, queryset):
        v = self.value()
        if not v:
            return queryset
        if v == 'none':
            return queryset.filter(registration_source__isnull=True)
        return queryset.filter(registration_source__source_type=v)


@admin.register(Partner)
class PartnerAdmin(ModelAdmin):
    """Admin for Partner model — external referral partners."""
    list_display = ['name', 'referral_code', 'referral_link_display', 'referred_count', 'fully_referred_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'referral_code']
    readonly_fields = ['referral_code', 'referral_link_display', 'referred_count', 'fully_referred_count', 'created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'is_active'),
        }),
        ('Referal', {
            'fields': ('referral_code', 'referral_link_display', 'referred_count', 'fully_referred_count'),
        }),
        ('Vaqt', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @display(description="Havola")
    def referral_link_display(self, obj):
        from django.conf import settings
        bot_token = getattr(settings, 'BOT_TOKEN', '')
        if bot_token:
            import requests
            try:
                resp = requests.get(
                    f"https://api.telegram.org/bot{bot_token}/getMe", timeout=3
                ).json()
                bot_username = resp.get('result', {}).get('username', '')
                if bot_username:
                    return f"https://t.me/{bot_username}?start={obj.referral_code}"
            except Exception:
                pass
        return f"t.me/BOT?start={obj.referral_code}"

    @display(description="Foydalanuvchilar soni")
    def referred_count(self, obj):
        return obj.referred_students.count()

    @display(description="To'liq ro'yxatdan o'tganlar")
    def fully_referred_count(self, obj):
        return obj.fully_referred_students_count


@admin.register(Student)
class StudentAdmin(ModelAdmin):
    """Admin for Student model."""
    list_display = ['telegram_id', 'first_name', 'last_name', 'grade', 'is_fully_registered_display', 'last_test_score_display', 'referral_points', 'school_name', 'is_active', 'created_at']
    list_filter = ['grade', 'is_active', 'registered_from_web', RegistrationStepFilter, RegistrationSourceFilter, FullyRegisteredFilter, LastTestAttemptScoreFilter, 'partner', 'created_at']
    search_fields = ['telegram_id', 'first_name', 'last_name', 'username', 'phone_number', 'school_name', 'referral_code']
    readonly_fields = ['created_at', 'updated_at', 'referral_points', 'referral_code', 'referrer', 'partner']
    ordering = ['-created_at']
    list_per_page = 50
    show_full_result_count = False
    actions = ['send_certificate_action', 'export_students_csv']

    def get_queryset(self, request):
        """Optimize queryset with select_related, prefetch_related, and only()."""
        qs = super().get_queryset(request)
        
        # Only fetch fields displayed in the list_display and filters
        qs = qs.only(
            'id', 'telegram_id', 'first_name', 'last_name', 'grade', 
            'is_active', 'created_at', 'referral_points', 'school_name',
            'registered_from_web', 'date_of_birth', 'referrer_id', 'partner_id'
        )
        
        # Use select_related for ForeignKey relationships
        qs = qs.select_related(
            'parent', 'teacher', 'referrer', 'partner'
        )
        
        # Optimize subquery for last test attempt score
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
    list_display = ['rank', 'first_name', 'last_name', 'telegram_id', 'referral_points', 'completed_referrals_display', 'total_referred_display']
    list_display_links = []  # no link to detail view
    actions = ['export_rating_csv']
    ordering = ['-referral_points', '-created_at']
    search_fields = ['first_name', 'last_name', 'telegram_id']
    list_per_page = 50
    show_full_result_count = False

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .filter(is_active=True)
            .exclude(Q(first_name__isnull=True) | Q(first_name=''))
            .annotate(
                last_referral_at=Coalesce(
                    Max('referrals_made__created_at'),
                    F('created_at'),
                ),
                computed_rank=Window(
                    expression=RowNumber(),
                    order_by=[
                        F('referral_points').desc(),
                        F('last_referral_at').asc(),
                    ]
                ),
                total_referred_count=Count('referred_students', distinct=True)
            )
        )
    
    def get_completed_referrals_count(self, obj):
        """Count referred students who completed registration (have all required fields)."""
        return obj.referred_students.filter(
            is_active=True,
            first_name__gt='',
            last_name__isnull=False,
        ).exclude(
            last_name=''
        ).filter(
            phone_number__isnull=False,
            phone_number__gt='',
            grade__isnull=False,
            document_number__isnull=False,
            document_number__gt='',
        ).count()

    @display(description='#')
    def rank(self, obj):
        return getattr(obj, 'computed_rank', '')

    @display(description="To'liq ro'yxatdan o'tganlar")
    def completed_referrals_display(self, obj):
        return self.get_completed_referrals_count(obj)

    @display(description="Jami taklif qilinganlar")
    def total_referred_display(self, obj):
        return getattr(obj, 'total_referred_count', 0)

    def export_rating_csv(self, request, queryset):
        """Export selected rating entries to CSV with rank."""
        if not queryset.exists():
            self.message_user(request, "Eksport qilish uchun kamida bitta qatorni tanlang.", level=messages.WARNING)
            return

        # Re-annotate to ensure we have computed rank and total_referred_count
        # We reuse the logic from get_queryset but for the specific queryset
        from django.db.models import Window, F, Max, Count
        from django.db.models.functions import RowNumber, Coalesce
        
        qs = queryset.annotate(
            last_referral_at=Coalesce(
                Max('referrals_made__created_at'),
                F('created_at'),
            ),
            computed_rank=Window(
                expression=RowNumber(),
                order_by=[
                    F('referral_points').desc(),
                    F('last_referral_at').asc(),
                ]
            ),
            total_referred_count=Count('referred_students', distinct=True)
        )

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        # Header row
        headers = [
            'Rank', 'First Name', 'Last Name', 'Telegram ID', 'Referral Points', 
            'Fully Registered Referrals', 'Total Referrals'
        ]
        writer.writerow(headers)

        for obj in qs:
            row = [
                getattr(obj, 'computed_rank', ''),
                obj.first_name or "",
                obj.last_name or "",
                obj.telegram_id,
                obj.referral_points or 0,
                self.get_completed_referrals_count(obj),
                getattr(obj, 'total_referred_count', 0),
            ]
            writer.writerow(row)

        response = HttpResponse(
            buffer.getvalue().encode('utf-8-sig'),
            content_type='text/csv; charset=utf-8-sig'
        )
        response['Content-Disposition'] = 'attachment; filename="student_rating.csv"'
        return response

    export_rating_csv.short_description = "Tanlangan reytingni CSV ga eksport qilish"


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
    actions = ['export_teachers_csv']

    def export_teachers_csv(self, request, queryset):
        """Export selected teachers to CSV."""
        if not queryset.exists():
            self.message_user(request, "Eksport qilish uchun kamida bitta o'qituvchini tanlang.", level=messages.WARNING)
            return

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        
        headers = [
            'O\'qituvchi FIO', 'Telefon raqam', 'Ish joyi', 'O\'quvchi', 'Yaratilgan vaqt'
        ]
        writer.writerow(headers)

        for obj in queryset:
            student_name = obj.student.first_name + " " + (obj.student.last_name or "") if obj.student else ""
            row = [
                obj.full_name or "",
                obj.phone_number or "",
                obj.workplace or "",
                student_name.strip(),
                obj.created_at.strftime("%Y-%m-%d %H:%M") if obj.created_at else "",
            ]
            writer.writerow(row)

        response = HttpResponse(
            buffer.getvalue().encode('utf-8-sig'),
            content_type='text/csv; charset=utf-8-sig'
        )
        response['Content-Disposition'] = 'attachment; filename="teachers.csv"'
        return response

    export_teachers_csv.short_description = "Tanlanganlarni CSV ga eksport qilish"


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
    list_display = ['title', 'grade', 'language', 'version', 'duration_minutes', 'questions_count', 'sent_count', 'blocked_count', 'is_active', 'created_at']
    list_filter = ['grade', 'language', 'is_active', 'created_at']
    search_fields = ['title', 'version']
    readonly_fields = ['created_at', 'updated_at', 'questions_count', 'sent_count', 'blocked_count', 'blocked_users_display']
    ordering = ['grade', 'title', 'version']
    inlines = [TestQuestionInline]
    actions = ['send_test_to_students_action']
    filter_horizontal = ['target_students']
    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('title', 'grade', 'target_students', 'language', 'version', 'duration_minutes', 'is_active', "starts_at", "finish_at")
        }),
        ('Yuborish statistikasi', {
            'fields': ('sent_count', 'blocked_count', 'blocked_users_display'),
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

    @display(description="Bloklagan foydalanuvchilar")
    def blocked_users_display(self, obj):
        """Render blocked_users JSON list as human-readable text."""
        if not obj.blocked_users:
            return "—"
        lines = []
        for entry in obj.blocked_users:
            tid = entry.get('telegram_id', '?')
            name = entry.get('name', '')
            lines.append(f"{tid} — {name}" if name else str(tid))
        return "\n".join(lines)

    def send_test_to_students_action(self, request, queryset):
        """Assign test to students (create PENDING attempt) and send Telegram notification.
        
        Runs the actual sending in a background thread so the admin UI responds immediately.
        Updates sent_count, blocked_count, and blocked_users on the Test model.
        """
        if queryset.count() != 1:
            self.message_user(
                request,
                "Iltimos, faqat bitta testni tanlang.",
                level=messages.ERROR
            )
            return

        test = queryset.first()

        if not test.is_active:
            self.message_user(
                request,
                "❌ Bu test faol emas. Yuborish uchun avval testni faollashtiring (Faol ✓).",
                level=messages.ERROR
            )
            return

        if test.get_questions_count() == 0:
            self.message_user(
                request,
                "Testda savollar yo'q. Avval savollar qo'shing, keyin yuboring.",
                level=messages.ERROR
            )
            return


        if test.grade is not None:
            query = Q(grade=test.grade, is_active=True)
            students = [s for s in Student.objects.filter(query) if s.is_fully_registered]
        else:
            students = [s for s in test.target_students.filter(is_active=True) if s.is_fully_registered]
            if not students:
                self.message_user(
                    request,
                    "Sinf bo'sh yoki to'liq ro'yxatdan o'tgan o'quvchilar yo'q. Iltimos, tanlangan o'quvchilarni qo'shing yoki sinfni tanlang.",
                    level=messages.ERROR
                )
                return

        available_tests = Test.objects.filter(grade=test.grade, is_active=True) if test.grade is not None else None
        available_languages = []
        if available_tests is not None:
            available_languages = sorted({t.language for t in available_tests if t.language})

        test_id = test.id  # capture before background thread

        def _do_send_in_background():
            """Background thread: send to each student, track stats, save to DB."""
            import django
            django.setup() if not django.conf.settings.configured else None

            new_sent = 0
            new_blocked = 0
            new_blocked_users = list(test.blocked_users or [])
            existing_blocked_ids = {entry.get('telegram_id') for entry in new_blocked_users}

            for student in students:
                if available_languages and len(available_languages) > 1:
                    attempt_exists = TestAttempt.objects.filter(
                        student=student,
                        status__in=['PENDING', 'IN_PROGRESS', 'FINISHED_REVIEW'],
                        test__grade=test.grade,
                    ).exists()
                else:
                    attempt_exists = TestAttempt.objects.filter(
                        test=test,
                        student=student,
                        status__in=['PENDING', 'IN_PROGRESS', 'FINISHED_REVIEW'],
                    ).exists()

                if attempt_exists:
                    continue

                attempt = None
                try:
                    if available_languages and len(available_languages) > 1:
                        send_test_assignment_message(
                            student.telegram_id,
                            test,
                            with_start_button=False,
                            language_options=available_languages,
                        )
                    else:
                        attempt = TestAttempt.objects.create(
                            student=student,
                            test=test,
                            status='PENDING',
                            started_at=None,
                            expires_at=None,
                        )
                        send_test_assignment_message(student.telegram_id, test, with_start_button=True)
                    new_sent += 1

                    # Throttle: 1 message per second to avoid rate limiting
                    time.sleep(1.0)

                except Exception as e:
                    err_str = str(e).lower()
                    is_blocked = (
                        "forbidden" in err_str
                        or "blocked" in err_str
                        or "user is deactivated" in err_str
                        or "bot was blocked" in err_str
                    )
                    if is_blocked:
                        new_blocked += 1
                        if student.telegram_id not in existing_blocked_ids:
                            existing_blocked_ids.add(student.telegram_id)
                            name = f"{student.first_name or ''} {student.last_name or ''}".strip()
                            new_blocked_users.append({
                                'telegram_id': student.telegram_id,
                                'name': name,
                                'username': student.username or '',
                            })
                    else:
                        logger.error(
                            "Failed to send test to student %s (ID: %s): %s",
                            student.first_name, student.telegram_id, e, exc_info=True
                        )
                    if attempt:
                        attempt.delete()

            # Save aggregated stats back to the Test model
            try:
                t = Test.objects.get(pk=test_id)
                t.sent_count = (t.sent_count or 0) + new_sent
                t.blocked_count = (t.blocked_count or 0) + new_blocked
                t.blocked_users = new_blocked_users
                t.save(update_fields=['sent_count', 'blocked_count', 'blocked_users'])
                logger.info(
                    "Test #%s send completed: sent=%s blocked=%s",
                    test_id, new_sent, new_blocked,
                )
            except Exception as save_err:
                logger.error("Failed to save test send stats: %s", save_err)

        thread = threading.Thread(target=_do_send_in_background, daemon=True)
        thread.start()

        student_count = len(students)
        self.message_user(
            request,
            f"✅ Test {student_count} ta o'quvchiga yuborilmoqda (fon rejimida). "
            f"Statistikani ko'rish uchun testni yangilang.",
            level=messages.SUCCESS
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

from admin_panel.registration_filters import REGISTRATION_STEP_CHOICES


class BroadcastMessageAdminForm(forms.ModelForm):
    """Form for BroadcastMessage with multi-select for registration steps."""
    target_registration_steps = forms.MultipleChoiceField(
        choices=REGISTRATION_STEP_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Ro'yxatdan o'tish bosqichi bo'yicha",
        help_text="Tanlangan bosqichlarda to'xtab qolgan o'quvchilarga yuborish.",
    )

    class Meta:
        model = BroadcastMessage
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial['target_registration_steps'] = self.instance.target_registration_steps or []

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.target_registration_steps = self.cleaned_data.get('target_registration_steps') or []
        if commit:
            obj.save()
        return obj


class BroadcastMediaInline(TabularInline):
    """Inline for media files attached to a broadcast."""
    model = BroadcastMedia
    extra = 1
    fields = ['media_type', 'file', 'order', 'duration', 'width', 'height', 'thumbnail']
    readonly_fields = ['duration', 'width', 'height', 'thumbnail']
    ordering = ['order']

    def has_change_permission(self, request, obj=None):
        if obj and obj.status != 'draft':
            return False
        return super().has_change_permission(request, obj)

    def has_add_permission(self, request, obj=None):
        if obj and obj.status != 'draft':
            return False
        return super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.status != 'draft':
            return False
        return super().has_delete_permission(request, obj)


@admin.register(BroadcastMessage)
class BroadcastMessageAdmin(ModelAdmin):
    """Admin for BroadcastMessage."""
    form = BroadcastMessageAdminForm
    list_display = ['created_at', 'status', 'media_count_display', 'recipient_count', 'sent_count', 'blocked_count', 'failed_count']
    list_filter = ['status', 'created_at']
    readonly_fields = [
        'status', 'recipient_count', 'sent_count', 'blocked_count', 
        'failed_count', 'error_log', 'started_at', 'completed_at', 'created_at'
    ]
    inlines = [BroadcastMediaInline]
    actions = ['send_broadcast_action']

    @display(description='Media')
    def media_count_display(self, obj):
        count = obj.media_files.count()
        return f"{count} ta" if count else "-"

    def get_readonly_fields(self, request, obj=None):
        """Make fields readonly if not draft."""
        if obj and obj.status != 'draft':
            return [f.name for f in self.model._meta.fields]
        return self.readonly_fields

    def send_broadcast_action(self, request, queryset):
        """Send filtered messages in a background thread (non-blocking)."""
        count = 0
        for broadcast in queryset:
            if broadcast.status != 'draft':
                self.message_user(request, f"Xabarnoma {broadcast.id} oxiriga yetkazilmagan (Holat: {broadcast.status})", level=messages.WARNING)
                continue

            broadcast.status = 'sending'
            broadcast.started_at = timezone.now()
            broadcast.save()

            thread = threading.Thread(
                target=self._run_broadcast_background,
                args=(broadcast.id, settings.BOT_TOKEN),
                daemon=True,
            )
            thread.start()
            count += 1

        if count:
            self.message_user(
                request,
                f"{count} ta xabarnoma yuborish boshlandi. Jarayonni ro'yxatda kuzatishingiz mumkin.",
                level=messages.SUCCESS,
            )

    send_broadcast_action.short_description = "Xabarnomani yuborish"

    @staticmethod
    def _run_broadcast_background(broadcast_id, bot_token):
        """Run broadcast in a background thread with its own event loop."""
        import asyncio

        async def _send():
            bot = Bot(token=bot_token)
            try:
                await BroadcastService.send_broadcast(broadcast_id, bot)
            finally:
                try:
                    await bot.session.close()
                except Exception:
                    pass

        try:
            asyncio.run(_send())
        except Exception as e:
            logger.error("Background broadcast %s failed: %s", broadcast_id, e)
            try:
                BroadcastMessage.objects.filter(id=broadcast_id).update(status='failed')
            except Exception:
                pass
        finally:
            from django.db import connection
            connection.close()

