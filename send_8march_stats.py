import os
import csv
import requests
import django

# Setup django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "exam_bot_admin.settings")
django.setup()

from django.conf import settings
from django.utils import timezone
from admin_panel.models import TestAttempt

# Get attempts: status SUBMITTED_FINAL and for tests created on March 8, 2026.
attempts = TestAttempt.objects.filter(
    status='SUBMITTED_FINAL',
    test__created_at__date=timezone.datetime(2026, 3, 8).date()
).select_related('student', 'test', 'student__teacher')

filename = '8_march_submitted_stats.csv'
with open(filename, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow([
        "Ismi", 
        "Familiyasi", 
        "sinfi maktabi", 
        "viloyati", 
        "telefon nomer", 
        "seriya raqam", 
        "tog'ri javoblar soni", 
        "tog'ri javoblar foizi", 
        "ustozi ismi", 
        "ustozi telefon raqami", 
        "test boshlagan vaqt", 
        "testni yakunlagan vaqt"
    ])
    
    for attempt in attempts:
        student = attempt.student
        teacher = getattr(student, 'teacher', None)
        
        grade_str = student.get_grade_display() if student.grade else ''
        school_str = student.school_name or ''
        sinfi_maktabi = f"{grade_str} {school_str}".strip()
        
        tz = timezone.get_current_timezone()
        started = attempt.started_at.astimezone(tz).strftime('%Y-%m-%d %H:%M:%S') if attempt.started_at else ''
        ended = attempt.submitted_at.astimezone(tz).strftime('%Y-%m-%d %H:%M:%S') if attempt.submitted_at else ''
        
        writer.writerow([
            student.first_name or '',
            student.last_name or '',
            sinfi_maktabi,
            student.get_region_display() if student.region else '',
            student.phone_number or '',
            student.document_number or '',
            attempt.earned_points if attempt.earned_points is not None else '',
            attempt.score if attempt.score is not None else '',
            teacher.full_name if teacher else '',
            teacher.phone_number if teacher else '',
            started,
            ended
        ])

print(f"Stats exported to {filename}. Total records: {attempts.count()}")

# Send via Telegram
bot_token = getattr(settings, 'BOT_TOKEN', None)
if not bot_token:
    # Try getting from env if settings.BOT_TOKEN is missing
    bot_token = os.environ.get('BOT_TOKEN')

if not bot_token:
    print("Error: Could not find BOT_TOKEN in settings or environment.")
    exit(1)

chat_id = "1535815443"
url = f"https://api.telegram.org/bot{bot_token}/sendDocument"

print(f"Sending document to user {chat_id}...")
with open(filename, 'rb') as doc:
    response = requests.post(
        url, 
        data={'chat_id': chat_id, 'caption': '8-mart test natijalari. Jami topshirganlar: ' + str(attempts.count())}, 
        files={'document': doc}
    )
    if response.status_code == 200:
        print(f"Successfully sent CSV to user {chat_id}!")
    else:
        print(f"Failed to send. Status: {response.status_code}, Response: {response.text}")

