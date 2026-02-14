"""Reusable registration step filtering logic for Student querysets."""
from django.db.models import Q

REGISTRATION_STEP_CHOICES = [
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
]


def filter_students_by_registration_step(queryset, step: str):
    """Filter Student queryset by registration step. Returns students at that step."""
    v = step
    if not v or v not in dict(REGISTRATION_STEP_CHOICES):
        return queryset.none()

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

    return queryset.none()


def filter_students_by_registration_steps(queryset, steps: list):
    """Filter Student queryset by one or more registration steps (OR: at any of these steps)."""
    if not steps:
        return queryset.none()

    pks = set()
    for step in steps:
        step_qs = filter_students_by_registration_step(queryset, step)
        pks.update(step_qs.values_list('pk', flat=True))

    return queryset.filter(pk__in=pks) if pks else queryset.none()
