import secrets
import string

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


def _generate_partner_code():
    """Generate a random 10-char alphanumeric partner referral code prefixed with 'ptr_'."""
    alphabet = string.ascii_letters + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(10))
    return f"ptr_{random_part}"


class Partner(models.Model):
    """External partner that brings users via a unique referral link."""
    name = models.CharField(max_length=255, verbose_name="Hamkor nomi")
    description = models.TextField(null=True, blank=True, verbose_name="Tavsif")
    referral_code = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        default=_generate_partner_code,
        verbose_name="Referal kodi",
        help_text="Avtomatik yaratiladi. t.me/BOT?start=ptr_XXXXXXXXXX",
    )
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")

    class Meta:
        db_table = 'partners'
        verbose_name = "Hamkor"
        verbose_name_plural = "Hamkorlar"
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def referred_students_count(self):
        return self.referred_students.count()


class Student(models.Model):
    REGION_CHOICES = [
        ('Andijon', 'Andijon viloyati'),
        ('Buxoro', 'Buxoro viloyati'),
        ('Farg\'ona', 'Farg\'ona viloyati'),
        ('Jizzax', 'Jizzax viloyati'),
        ('Namangan', 'Namangan viloyati'),
        ('Navoiy', 'Navoiy viloyati'),
        ('Qashqadaryo', 'Qashqadaryo viloyati'),
        ('Samarqand', 'Samarqand viloyati'),
        ('Sirdaryo', 'Sirdaryo viloyati'),
        ('Surxondaryo', 'Surxondaryo viloyati'),
        ('Toshkent', 'Toshkent viloyati'),
        ('Toshkent shahar', 'Toshkent shahar'),
        ('Xorazm', 'Xorazm viloyati'),
        ('Qoraqalpog\'iston', 'Qoraqalpog\'iston')
    ]
    GRADE_CHOICES = [
        (5, '5-sinf'),
        (6, '6-sinf'),
        (7, '7-sinf'),
        (8, '8-sinf'),
        (0, 'Boshqa'),
    ]
    LANGUAGE_CHOICES = [
        ('uz', 'O\'zbek'),
        ('ru', 'Rus'),
        ('en', 'Ingliz'),
    ]
    telegram_id = models.BigIntegerField(unique=True, db_index=True, verbose_name="Telegram ID")
    username = models.CharField(max_length=255, null=True, blank=True, verbose_name="Foydalanuvchi nomi")
    first_name = models.CharField(max_length=255, verbose_name="Ism")
    last_name = models.CharField(max_length=255, null=True, blank=True, verbose_name="Familiya")
    middle_name = models.CharField(max_length=255, null=True, blank=True, verbose_name="Sharif")
    phone_number = models.CharField(max_length=20, null=True, blank=True, verbose_name="Telefon raqami")
    grade = models.IntegerField(
        null=True,
        blank=True,
        choices=GRADE_CHOICES,
        verbose_name="Sinf"
    )
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="Tug'ilgan sanasi")
    region = models.CharField(max_length=255, choices=REGION_CHOICES, null=True, blank=True, verbose_name="Viloyat")
    district = models.CharField(max_length=255, null=True, blank=True, verbose_name="Tuman/shahar")
    language = models.CharField(max_length=50, choices=LANGUAGE_CHOICES, null=True, blank=True, verbose_name="Til")
    photo = models.ImageField(upload_to='students/', max_length=500, null=True, blank=True, verbose_name="Rasm")
    document_number = models.CharField(max_length=255, unique=True, null=True, blank=True, verbose_name="Metrika raqami")
    school_name = models.CharField(max_length=500, null=True, blank=True, verbose_name="Maktab nomi")
    referral_code = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Referral kodi",
        help_text="Do'stlarni taklif qilish havolasida ishlatiladi (admin tomonidan tahrirlanmaydi)",
    )
    
    # New fields for Stage 1 Registration
    PHONE_OWNER_CHOICES = [
        ('ozimniki', "O'zimniki"),
        ('turmush_ortogim', "Turmush o'rtog'im"),
        ('boshqa', "Boshqa"),
    ]
    initial_full_name = models.CharField(max_length=255, null=True, blank=True, verbose_name="Ism-familiya (Registratsiya)")
    phone_owner = models.CharField(max_length=50, choices=PHONE_OWNER_CHOICES, null=True, blank=True, verbose_name="Telefon egasi")
    registered_from_web = models.BooleanField(default=False, verbose_name="Web App orqali ro'yxatdan o'tgan")

    referral_points = models.IntegerField(
        default=0,
        verbose_name="Referral ballari",
        help_text="Har bir taklif qilingan do'st uchun 5 ball (admin tomonidan tahrirlanmaydi)",
    )
    referrer = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referred_students',
        verbose_name="Taklif qiluvchi",
        help_text="Bu foydalanuvchi qaysi student havolasi orqali kelgan (DB da saqlanadi)",
    )
    partner = models.ForeignKey(
        Partner,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referred_students',
        verbose_name="Hamkor",
        help_text="Foydalanuvchi qaysi hamkor havolasi orqali kelgan",
    )
    achievements_description = models.TextField(null=True, blank=True, verbose_name="Avvalgi yutuqlar izohi")
    achievements_file = models.FileField(upload_to='students/achievements/', max_length=500, null=True, blank=True, verbose_name="Avvalgi yutuqlar fayli/rasmi")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    state = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Ro'yxatdan o'tish holati",
        help_text="Foydalanuvchi qaysi qadamda ekanligi (bot tomonidan avtomatik yangilanadi)",
    )

    class Meta:
        db_table = 'students'
        verbose_name = "O'quvchi"
        verbose_name_plural = "O'quvchilar"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['telegram_id']),
            models.Index(fields=['grade']),
            models.Index(fields=['is_active', 'created_at']),
            models.Index(fields=['grade', 'is_active']),
            models.Index(fields=['referrer']),
            models.Index(fields=['partner']),
            models.Index(fields=['registered_from_web']),
        ]

    def save(self, *args, **kwargs):
        """Override save to ensure uppercase fields."""
        if self.first_name:
            self.first_name = self.first_name.upper()
        if self.last_name:
            self.last_name = self.last_name.upper()
        if self.middle_name:
            self.middle_name = self.middle_name.upper()
        if self.document_number:
            self.document_number = self.document_number.upper()
        super().save(*args, **kwargs)

    @property
    def is_fully_registered(self):
        """True if Stage 2 registration is complete: core fields + parent and teacher with phone numbers,
        OR if user registered via the Web App."""
        if self.registered_from_web:
            return True
        if not (self.first_name and self.last_name and self.date_of_birth and self.document_number):
            return False
        try:
            parent = self.parent
            parent_has_phone = bool(
                (parent.phone_number and parent.phone_number.strip())
                or (parent.phone_number2 and parent.phone_number2.strip())
            )
            if not parent_has_phone:
                return False
        except Parent.DoesNotExist:
            return False
        try:
            teacher = self.teacher
            teacher_has_phone = bool(teacher.phone_number and teacher.phone_number.strip())
            if not teacher_has_phone:
                return False
        except Teacher.DoesNotExist:
            return False
        return True

    def __str__(self):
        return f"{self.first_name} {self.last_name or ''} (ID: {self.telegram_id})"


class StudentRating(Student):
    """Proxy model for admin: referral leaderboard (list only, no detail view)."""
    class Meta:
        proxy = True
        verbose_name = "Reyting"
        verbose_name_plural = "Reyting"
        ordering = ['-referral_points', '-created_at']


class Parent(models.Model):
    """Parent/guardian information."""
    RELATIONSHIP_CHOICES = [
        ('ota', 'Ota'),
        ('ona', 'Ona'),
        ('aka', 'Aka'),
        ('opa', 'Opa'),
        ('buvi', 'Buvi'),
        ('bobo', 'Bobo'),
        ('vasiy', 'Vasiy'),
        ('boshqa', 'Boshqa'),
    ]
    CHILDREN_COUNT_CHOICES = [
        (1, '1'),
        (2, '2'),
        (3, '3'),
        (4, '4'),
        (5, '5+'),
    ]
    student = models.OneToOneField(
        Student,
        on_delete=models.CASCADE,
        related_name='parent',
        verbose_name="O'quvchi"
    )
    full_name = models.CharField(max_length=255, verbose_name="To'liq ism")
    phone_number = models.CharField(max_length=20, null=True, blank=True, verbose_name="Telefon raqami 1")
    phone_number2 = models.CharField(max_length=20, null=True, blank=True, verbose_name="Telefon raqami 2")
    relationship = models.CharField(
        max_length=50,
        choices=RELATIONSHIP_CHOICES,
        null=True,
        blank=True,
        verbose_name="Kimligi"
    )
    age = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(150)],
        verbose_name="Yoshi"
    )
    children_count = models.IntegerField(
        null=True,
        blank=True,
        choices=CHILDREN_COUNT_CHOICES,
        verbose_name="Farzandlar soni"
    )
    profession = models.CharField(max_length=255, null=True, blank=True, verbose_name="Kasbi")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")

    class Meta:
        db_table = 'parents'
        verbose_name = "Ota-ona"
        verbose_name_plural = "Ota-onalar"

    def __str__(self):
        return f"{self.full_name} - {self.student.first_name}'s parent"


class Teacher(models.Model):
    """Teacher information."""
    student = models.OneToOneField(
        Student,
        on_delete=models.CASCADE,
        related_name='teacher',
        verbose_name="O'quvchi"
    )
    full_name = models.CharField(max_length=255, verbose_name="To'liq ism")
    phone_number = models.CharField(max_length=20, null=True, blank=True, verbose_name="Telefon raqami")
    workplace = models.CharField(max_length=255, null=True, blank=True, verbose_name="Ish joyi")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")

    class Meta:
        db_table = 'teachers'
        verbose_name = "O'qituvchi"
        verbose_name_plural = "O'qituvchilar"

    def __str__(self):
        return f"{self.full_name} - {self.student.first_name}'s teacher"


class Referral(models.Model):
    """Referral: when a user signs up via another user's link, referrer earns points."""
    referrer = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='referrals_made',
        verbose_name="Taklif qiluvchi",
    )
    referred = models.OneToOneField(
        Student,
        on_delete=models.CASCADE,
        related_name='referred_by',
        verbose_name="Ro'yxatdan o'tgan",
    )
    points_earned = models.IntegerField(default=5, verbose_name="Olingan ball")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")

    class Meta:
        db_table = 'referrals'
        verbose_name = "Referral"
        verbose_name_plural = "Referrallar"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['referrer']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.referrer.first_name} → {self.referred.first_name}"


class RegistrationSource(models.Model):
    """Source of registration (e.g., referral, advertisement)."""
    SOURCE_TYPE_CHOICES = [
        ('by_rahimov_school', 'Rahimov School sahifalaridan'),
        ('instagram', 'Instagram'),
        ('telegram_ads', 'Telegram Ads'),
        ('telegram_channel', 'Telegram kanal'),
        ('by_friend', 'Tanish orqali'),
        ('boshqa', 'Boshqa'),
    ]
    student = models.OneToOneField(
        Student,
        on_delete=models.CASCADE,
        related_name='registration_source',
        verbose_name="O'quvchi"
    )
    source_type = models.CharField(
        max_length=100,
        choices=SOURCE_TYPE_CHOICES,
        verbose_name="Manba turi"
    )
    source_details = models.TextField(null=True, blank=True, verbose_name="Manba tafsilotlari")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")

    class Meta:
        db_table = 'registration_sources'
        verbose_name = "Ro'yxatdan o'tish manbasi"
        verbose_name_plural = "Ro'yxatdan o'tish manbalari"

    def __str__(self):
        return f"{self.student.first_name} - {self.source_type}"


class Exam(models.Model):
    """Exam/test definition."""
    GRADE_CHOICES = [
        (5, '5-sinf'),
        (6, '6-sinf'),
        (7, '7-sinf'),
        (8, '8-sinf'),
    ]

    title = models.CharField(max_length=255, verbose_name="Sarlavha")
    description = models.TextField(null=True, blank=True, verbose_name="Tavsif")
    grade = models.IntegerField(choices=GRADE_CHOICES, verbose_name="Sinf")
    duration_minutes = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Imtihon davomiyligi daqiqalarda",
        verbose_name="Davomiyligi (daqiqa)"
    )
    total_questions = models.IntegerField(validators=[MinValueValidator(1)], verbose_name="Jami savollar")
    passing_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="O'tish uchun minimal foiz",
        verbose_name="O'tish balli (%)"
    )
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")

    class Meta:
        db_table = 'exams'
        verbose_name = "Imtihon"
        verbose_name_plural = "Imtihonlar"
        ordering = ['grade', 'title']
        indexes = [
            models.Index(fields=['grade', 'is_active']),
        ]

    def __str__(self):
        return f"{self.title} (Grade {self.grade})"


class Question(models.Model):
    """Question in an exam."""
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name="Imtihon"
    )
    question_text = models.TextField(verbose_name="Savol matni")
    question_number = models.IntegerField(validators=[MinValueValidator(1)], verbose_name="Savol raqami")
    correct_answer = models.CharField(max_length=255, verbose_name="To'g'ri javob")
    points = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Ball"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")

    class Meta:
        db_table = 'questions'
        verbose_name = "Savol"
        verbose_name_plural = "Savollar"
        ordering = ['exam', 'question_number']
        unique_together = [['exam', 'question_number']]
        indexes = [
            models.Index(fields=['exam', 'question_number']),
        ]

    def __str__(self):
        return f"Q{self.question_number}: {self.question_text[:50]}..."


class ExamAttempt(models.Model):
    """Student's attempt at an exam."""
    STATUS_CHOICES = [
        ('pending', 'Kutilmoqda'),
        ('in_progress', 'Jarayonda'),
        ('completed', 'Tugallangan'),
        ('expired', 'Muddati tugagan'),
        ('cancelled', 'Bekor qilingan'),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='exam_attempts',
        verbose_name="O'quvchi"
    )
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='attempts',
        verbose_name="Imtihon"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Holat")
    score = models.IntegerField(null=True, blank=True, help_text="Foizda ball", verbose_name="Ball (%)")
    total_points = models.IntegerField(null=True, blank=True, verbose_name="Jami ball")
    earned_points = models.IntegerField(null=True, blank=True, verbose_name="Olingan ball")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="Boshlangan vaqt")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Tugallangan vaqt")
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="Muddati tugaydi")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")

    class Meta:
        db_table = 'exam_attempts'
        verbose_name = "Imtihon topshirish"
        verbose_name_plural = "Imtihon topshirishlar"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['exam', 'status']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.student.first_name} - {self.exam.title} ({self.status})"

    def is_expired(self):
        """Check if the exam attempt has expired."""
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False


class Answer(models.Model):
    """Student's answer to a question."""
    attempt = models.ForeignKey(
        ExamAttempt,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name="Imtihon topshirish"
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name="Savol"
    )
    answer_text = models.CharField(max_length=255, verbose_name="Javob matni")
    is_correct = models.BooleanField(default=False, verbose_name="To'g'ri")
    points_earned = models.IntegerField(default=0, verbose_name="Olingan ball")
    answered_at = models.DateTimeField(auto_now_add=True, verbose_name="Javob berilgan vaqt")

    class Meta:
        db_table = 'answers'
        verbose_name = "Javob"
        verbose_name_plural = "Javoblar"
        unique_together = [['attempt', 'question']]
        indexes = [
            models.Index(fields=['attempt', 'question']),
        ]

    def __str__(self):
        return f"Answer to Q{self.question.question_number} - {'Correct' if self.is_correct else 'Incorrect'}"


class Certificate(models.Model):
    """Generated certificate for a student."""
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='certificates',
        verbose_name="O'quvchi"
    )
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='certificates',
        verbose_name="Imtihon"
    )
    attempt = models.OneToOneField(
        ExamAttempt,
        on_delete=models.CASCADE,
        related_name='certificate',
        verbose_name="Imtihon topshirish"
    )
    certificate_number = models.CharField(max_length=100, unique=True, db_index=True, verbose_name="Sertifikat raqami")
    pdf_path = models.CharField(max_length=500, null=True, blank=True, verbose_name="PDF fayl yo'li")
    image_path = models.CharField(max_length=500, null=True, blank=True, verbose_name="Rasm yo'li")
    generated_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")

    class Meta:
        db_table = 'certificates'
        verbose_name = "Sertifikat"
        verbose_name_plural = "Sertifikatlar"
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['student']),
            models.Index(fields=['certificate_number']),
        ]

    def __str__(self):
        return f"Certificate {self.certificate_number} - {self.student.first_name}"


class Feedback(models.Model):
    """Student feedback."""
    TYPE_CHOICES = [
        ('suggestion', 'Taklif'),
        ('complaint', 'Shikoyat'),
    ]
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='feedbacks',
        verbose_name="O'quvchi"
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='suggestion', verbose_name="Turi")
    text = models.TextField(verbose_name="Matn")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")

    class Meta:
        db_table = 'feedbacks'
        verbose_name = "Fikr-mulohaza"
        verbose_name_plural = "Fikr-mulohazalar"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['student']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.get_type_display()} form {self.student.first_name} - {self.created_at.strftime('%d.%m.%Y')}"


class BotState(models.Model):
    """FSM state for bot conversations."""
    telegram_id = models.BigIntegerField(unique=True, db_index=True, verbose_name="Telegram ID")
    state = models.CharField(max_length=100, null=True, blank=True, verbose_name="Holat")
    state_data = models.JSONField(default=dict, blank=True, verbose_name="Holat ma'lumotlari")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")

    class Meta:
        db_table = 'bot_states'
        verbose_name = "Bot holati"
        verbose_name_plural = "Bot holatlari"
        indexes = [
            models.Index(fields=['telegram_id']),
            models.Index(fields=['state']),
        ]

    def __str__(self):
        return f"State for {self.telegram_id}: {self.state or 'None'}"


class Test(models.Model):
    """Test definition with grade-based separation."""
    GRADE_CHOICES = [
        (5, '5-sinf'),
        (6, '6-sinf'),
        (7, '7-sinf'),
        (8, '8-sinf'),
    ]
    LANGUAGE_CHOICES = [
        ('uz', 'O\'zbek'),
        ('ru', 'Rus'),
        ('en', 'Ingliz'),
    ]

    title = models.CharField(max_length=255, verbose_name="Nomi")
    grade = models.IntegerField(
        choices=GRADE_CHOICES,
        null=True,
        blank=True,
        verbose_name="Sinf",
        help_text="Ixtiyoriy. Bo'sh qoldirsangiz, testni faqat tanlangan o'quvchilarga yuborishingiz mumkin."
    )
    target_students = models.ManyToManyField(
        Student,
        related_name='targeted_tests',
        blank=True,
        verbose_name="Tanlangan o'quvchilar",
        help_text="Sinf bo'sh bo'lsa, test shu o'quvchilarga yuboriladi."
    )
    language = models.CharField(
        max_length=50,
        choices=LANGUAGE_CHOICES,
        null=True,
        blank=True,
        verbose_name="Til",
        help_text="Test tili (ixtiyoriy)"
    )
    duration_minutes = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Test davomiyligi daqiqalarda",
        verbose_name="Davomiyligi (daqiqa)"
    )
    version = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Test versiyasi (masalan: v1, v2) - bir sinfga bir nechta test bo'lishi uchun",
        verbose_name="Versiya"
    )
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    starts_at = models.DateTimeField(null=True, blank=True, verbose_name="Boshlanish vaqti", help_text="Agar belgilansa, test faqat shu vaqtdan keyin boshlanishi mumkin.")
    finish_at = models.DateTimeField(null=True, blank=True, verbose_name="Tugash vaqti", help_text="Agar belgilansa, test faqat shu vaqtdan oldin boshlanishi mumkin.")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")

    class Meta:
        db_table = 'tests'
        verbose_name = "Test"
        verbose_name_plural = "Testlar"
        ordering = ['grade', 'title', 'version']
        indexes = [
            models.Index(fields=['grade', 'is_active']),
            models.Index(fields=['grade', 'version']),
        ]

    def __str__(self):
        version_str = f" ({self.version})" if self.version else ""
        grade_str = self.get_grade_display() if self.grade is not None else "Maxsus"
        return f"{self.title} - {grade_str}{version_str}"

    def get_questions_count(self):
        """Return the number of questions in this test."""
        return self.questions.count()


class TestQuestion(models.Model):
    """Question in a test with multiple choice options."""
    ANSWER_CHOICES = [
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
    ]

    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name="Test"
    )
    question_number = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Savol raqami"
    )
    text = models.TextField(
        verbose_name="Savol matni",
        blank=True,
        null=True,
    )
    image = models.ImageField(
        upload_to='questions/',
        null=True,
        blank=True,
        verbose_name="Savol rasmi",
        help_text="Agar rasm bo'lsa, savol matni rasm ostida caption sifatida yuboriladi.",
    )
    option_a = models.CharField(
        max_length=500,
        verbose_name="Variant A",
        blank=True,
        null=True,
    )
    option_b = models.CharField(
        max_length=500,
        verbose_name="Variant B",
        blank=True,
        null=True,
    )
    option_c = models.CharField(
        max_length=500,
        verbose_name="Variant C",
        blank=True,
        null=True,
    )
    option_d = models.CharField(
        max_length=500,
        verbose_name="Variant D",
        blank=True,
        null=True,
    )
    correct_answer = models.CharField(
        max_length=1,
        choices=ANSWER_CHOICES,
        verbose_name="To'g'ri javob"
    )
    ball_weight = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        null=True,
        blank=True,
        help_text="Savolning og'irligi (ball)",
        verbose_name="Ball og'irligi"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")

    class Meta:
        db_table = 'test_questions'
        verbose_name = "Test savoli"
        verbose_name_plural = "Test savollari"
        ordering = ['test', 'question_number']
        unique_together = [['test', 'question_number']]
        indexes = [
            models.Index(fields=['test', 'question_number']),
        ]

    def __str__(self):
        return f"Q{self.question_number}: {self.text[:50]}... ({self.test.title})"

    def get_options_dict(self):
        """Return options as a dictionary."""
        return {
            'A': self.option_a,
            'B': self.option_b,
            'C': self.option_c,
            'D': self.option_d,
        }


class TestAttempt(models.Model):
    """Student's attempt at a test."""
    STATUS_CHOICES = [
        ('PENDING', 'Kutilmoqda'),
        ('IN_PROGRESS', 'Jarayonda'),
        ('FINISHED_REVIEW', 'Tekshiruvda'),
        ('SUBMITTED_FINAL', 'Yakuniy topshirilgan'),
        ('TIME_EXPIRED', 'Vaqt tugagan'),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='test_attempts',
        verbose_name="O'quvchi"
    )
    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name='attempts',
        verbose_name="Test"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name="Holat"
    )
    score = models.FloatField(
        null=True,
        blank=True,
        help_text="Foizda ball",
        verbose_name="Ball (%)"
    )
    total_points = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Jami ball"
    )
    earned_points = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Olingan ball"
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Boshlangan vaqt"
    )
    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Topshirilgan vaqt"
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Muddati tugaydi"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Yaratilgan vaqt"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Yangilangan vaqt"
    )

    class Meta:
        db_table = 'test_attempts'
        verbose_name = "Test topshirish"
        verbose_name_plural = "Test topshirishlar"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['test', 'status']),
            models.Index(fields=['status']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"{self.student.first_name} - {self.test.title} ({self.status})"

    def is_expired(self):
        """Check if the test attempt has expired."""
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False

    def get_remaining_time_minutes(self):
        """Get remaining time in minutes."""
        if not self.expires_at:
            return None
        if self.is_expired():
            return 0
        delta = self.expires_at - timezone.now()
        return max(0, int(delta.total_seconds() / 60))


class TestAnswer(models.Model):
    """Student's answer to a test question."""
    attempt = models.ForeignKey(
        TestAttempt,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name="Test topshirish"
    )
    question = models.ForeignKey(
        TestQuestion,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name="Savol"
    )
    answer_choice = models.CharField(
        max_length=1,
        null=True,
        blank=True,
        choices=TestQuestion.ANSWER_CHOICES,
        verbose_name="Tanlangan javob"
    )
    is_correct = models.BooleanField(
        default=False,
        verbose_name="To'g'ri"
    )
    points_earned = models.FloatField(
        default=0.0,
        verbose_name="Olingan ball"
    )
    answered_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Javob berilgan vaqt"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Yangilangan vaqt"
    )

    class Meta:
        db_table = 'test_answers'
        verbose_name = "Test javobi"
        verbose_name_plural = "Test javoblari"
        unique_together = [['attempt', 'question']]
        indexes = [
            models.Index(fields=['attempt', 'question']),
        ]

    def __str__(self):
        answer_display = self.answer_choice if self.answer_choice else "—"
        return f"Answer to Q{self.question.question_number}: {answer_display} - {'Correct' if self.is_correct else 'Incorrect'}"


class MandatoryChannel(models.Model):
    """Channels that users must join."""
    title = models.CharField(max_length=255, verbose_name="Kanal nomi")
    channel_id = models.CharField(max_length=255, unique=True, verbose_name="Kanal ID/Username")
    channel_username = models.CharField(max_length=255, null=True, blank=True, verbose_name="Kanal havolasi (username)")
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")

    class Meta:
        db_table = 'mandatory_channels'
        verbose_name = "Majburiy kanal"
        verbose_name_plural = "Majburiy kanallar"

    def __str__(self):
        return self.title

    def clean(self):
        """Validate that the bot is an admin in the channel."""
        from django.core.exceptions import ValidationError
        import requests
        from django.conf import settings

        if not self.channel_id:
            return

        token = settings.BOT_TOKEN
        if not token:
            return

        # Prepare channel_id (add @ if it's a username)
        chat_id = self.channel_id
        if not chat_id.startswith('-') and not chat_id.startswith('@') and not chat_id.isdigit():
            chat_id = f"@{chat_id}"

        try:
            # 1. Get Bot ID
            get_me_url = f"https://api.telegram.org/bot{token}/getMe"
            me_resp = requests.get(get_me_url, timeout=5).json()
            if not me_resp.get('ok'):
                raise ValidationError(f"Bot token xatosi: {me_resp.get('description')}")
            
            bot_id = me_resp['result']['id']
            
            # 2. Check Bot Status in Chat
            member_url = f"https://api.telegram.org/bot{token}/getChatMember"
            member_resp = requests.get(member_url, params={'chat_id': chat_id, 'user_id': bot_id}, timeout=5).json()
            
            if not member_resp.get('ok'):
                raise ValidationError(f"Kanal topilmadi yoki bot kanal a'zosi emas: {member_resp.get('description')}")
            
            status = member_resp['result']['status']
            if status != 'administrator':
                raise ValidationError("Bot ushbu kanalda administrator emas. Iltimos, avval botni administrator qiling.")

            # 3. Auto-fill title/username if empty
            if not self.channel_username or not self.title:
                chat_url = f"https://api.telegram.org/bot{token}/getChat"
                chat_resp = requests.get(chat_url, params={'chat_id': chat_id}, timeout=5).json()
                if chat_resp.get('ok'):
                    chat = chat_resp['result']
                    if not self.channel_username and chat.get('username'):
                        self.channel_username = f"https://t.me/{chat['username']}"
                    elif not self.channel_username and chat.get('invite_link'):
                        self.channel_username = chat['invite_link']
                    
                    if not self.title and chat.get('title'):
                        self.title = chat['title']
                    
        except requests.RequestException as e:
             raise ValidationError(f"Telegram API bilan bog'lanishda xatolik: {str(e)}")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)



class BroadcastMessage(models.Model):
    """Message to broadcast to users."""
    STATUS_CHOICES = [
        ('draft', 'Qoralama'),
        ('sending', 'Yuborilmoqda'),
        ('completed', 'Yakunlandi'),
        ('failed', 'Xatolik'),
    ]

    target_all_users = models.BooleanField(
        default=False,
        verbose_name="Barcha foydalanuvchilarga",
        help_text="Belgilanganda xabar barcha faol foydalanuvchilarga yuboriladi (boshqa filtrlar hisobga olinmaydi).",
    )
    target_grade_5 = models.BooleanField(default=False, verbose_name="5-sinf")
    target_grade_6 = models.BooleanField(default=False, verbose_name="6-sinf")
    target_grade_7 = models.BooleanField(default=False, verbose_name="7-sinf")
    target_grade_8 = models.BooleanField(default=False, verbose_name="8-sinf")
    target_not_fully_registered = models.BooleanField(
        default=False,
        verbose_name="Faqat to'liq ro'yxatdan o'tmaganlarga",
        help_text="Belgilanganda xabar faqat to'liq ro'yxatdan o'tmagan o'quvchilarga yuboriladi (ota-ona va o'qituvchi telefonlari bo'yicha).",
    )
    target_registration_steps = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Ro'yxatdan o'tish bosqichi bo'yicha",
        help_text="Tanlangan bosqichlarda to'xtab qolgan o'quvchilarga yuborish. Bo'sh qoldirilsa, barcha bosqichlar hisobga olinmaydi (faqat sinf / to'liq ro'yxatdan o'tmagan filtrlari ishlatiladi).",
    )

    message = models.TextField(
        verbose_name="Xabar matni",
        help_text="HTML formatini qo'llab quvvatlaydi (<b>qalin</b>, <i>kursiv</i>, <a href='...'>havola</a>). {student_name} - o'quvchi ismi o'rniga tushadi."
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="Holat")
    
    # Statistics
    recipient_count = models.IntegerField(default=0, verbose_name="Qabul qiluvchilar")
    sent_count = models.IntegerField(default=0, verbose_name="Yuborildi")
    blocked_count = models.IntegerField(default=0, verbose_name="Bloklaganlar")
    failed_count = models.IntegerField(default=0, verbose_name="Xatoliklar")
    
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="Boshlangan vaqt")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Tugallangan vaqt")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")

    class Meta:
        db_table = 'broadcast_messages'
        verbose_name = "Xabarnoma"
        verbose_name_plural = "Xabarnomalar"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.created_at.strftime('%d.%m.%Y %H:%M')} - {self.get_status_display()}"

    def clean(self):
        from django.core.exceptions import ValidationError

        has_media = self.pk and self.media_files.exists()
        max_len = 1024 if has_media else 4096
        label = "Caption (media bilan)" if has_media else "Xabar matni"

        if self.message and len(self.message) > max_len:
            raise ValidationError({
                'message': f"{label} {max_len} belgidan oshmasligi kerak. Hozir: {len(self.message)}."
            })

        if self.pk and self.media_files.count() > 10:
            raise ValidationError("Maksimum 10 ta media fayl biriktirish mumkin.")


PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
VIDEO_EXTENSIONS = {'.mp4', '.mov'}
PHOTO_MAX_SIZE = 10 * 1024 * 1024   # 10 MB
VIDEO_MAX_SIZE = 50 * 1024 * 1024   # 50 MB


class BroadcastMedia(models.Model):
    """Media file attached to a broadcast message."""
    MEDIA_TYPE_CHOICES = [
        ('photo', 'Rasm'),
        ('video', 'Video'),
    ]

    broadcast = models.ForeignKey(
        BroadcastMessage,
        on_delete=models.CASCADE,
        related_name='media_files',
        verbose_name="Xabarnoma",
    )
    media_type = models.CharField(
        max_length=10,
        choices=MEDIA_TYPE_CHOICES,
        verbose_name="Media turi",
    )
    file = models.FileField(upload_to='broadcasts/', verbose_name="Fayl")
    order = models.PositiveIntegerField(default=0, verbose_name="Tartib")

    # Video metadata (auto-populated on save)
    duration = models.PositiveIntegerField(null=True, blank=True, verbose_name="Davomiylik (sek)")
    width = models.PositiveIntegerField(null=True, blank=True, verbose_name="Kenglik (px)")
    height = models.PositiveIntegerField(null=True, blank=True, verbose_name="Balandlik (px)")
    thumbnail = models.ImageField(
        upload_to='broadcasts/thumbs/', null=True, blank=True, verbose_name="Eskiz",
    )

    class Meta:
        db_table = 'broadcast_media'
        verbose_name = "Media"
        verbose_name_plural = "Media fayllar"
        ordering = ['order']

    def __str__(self):
        return f"{self.get_media_type_display()} #{self.order}"

    def clean(self):
        from django.core.exceptions import ValidationError
        import os

        if not self.file:
            return

        ext = os.path.splitext(self.file.name)[1].lower()
        size = self.file.size

        if self.media_type == 'photo':
            if ext not in PHOTO_EXTENSIONS:
                raise ValidationError({
                    'file': f"Rasm formati noto'g'ri. Ruxsat etilgan: {', '.join(sorted(PHOTO_EXTENSIONS))}"
                })
            if size > PHOTO_MAX_SIZE:
                raise ValidationError({
                    'file': f"Rasm hajmi {size // (1024*1024)} MB. Maksimum: 10 MB."
                })
        elif self.media_type == 'video':
            if ext not in VIDEO_EXTENSIONS:
                raise ValidationError({
                    'file': f"Video formati noto'g'ri. Ruxsat etilgan: {', '.join(sorted(VIDEO_EXTENSIONS))}"
                })
            if size > VIDEO_MAX_SIZE:
                raise ValidationError({
                    'file': f"Video hajmi {size // (1024*1024)} MB. Maksimum: 50 MB."
                })

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.media_type == 'video' and self.file and not self.duration:
            self._extract_video_metadata()

    def _extract_video_metadata(self):
        """Extract duration, dimensions, and generate thumbnail using ffprobe/ffmpeg."""
        import subprocess
        import json
        import os
        import logging

        logger = logging.getLogger(__name__)
        file_path = self.file.path

        if not os.path.isfile(file_path):
            return

        # Extract duration and dimensions via ffprobe
        try:
            result = subprocess.run(
                [
                    'ffprobe', '-v', 'quiet', '-print_format', 'json',
                    '-show_format', '-show_streams', file_path,
                ],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                probe = json.loads(result.stdout)
                for stream in probe.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        self.width = int(stream.get('width', 0)) or None
                        self.height = int(stream.get('height', 0)) or None
                        break
                dur = probe.get('format', {}).get('duration')
                if dur:
                    self.duration = int(float(dur))
        except Exception as e:
            logger.warning("ffprobe failed for %s: %s", file_path, e)

        # Generate thumbnail at 1-second mark
        thumb_dir = os.path.join(os.path.dirname(file_path), 'thumbs')
        os.makedirs(thumb_dir, exist_ok=True)
        thumb_filename = f"thumb_{self.pk}.jpg"
        thumb_path = os.path.join(thumb_dir, thumb_filename)

        try:
            subprocess.run(
                [
                    'ffmpeg', '-y', '-i', file_path,
                    '-ss', '00:00:01', '-vframes', '1',
                    '-vf', 'scale=320:-2',
                    thumb_path,
                ],
                capture_output=True, timeout=30,
            )
            if os.path.isfile(thumb_path):
                rel_path = os.path.join('broadcasts', 'thumbs', thumb_filename)
                self.thumbnail = rel_path
        except Exception as e:
            logger.warning("ffmpeg thumbnail failed for %s: %s", file_path, e)

        # Save metadata fields without triggering another _extract call
        type(self).objects.filter(pk=self.pk).update(
            duration=self.duration, width=self.width,
            height=self.height, thumbnail=self.thumbnail or '',
        )
