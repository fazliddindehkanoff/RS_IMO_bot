import os
import django
from admin_panel.models import Test, TestAttempt

print("All tests:")
for t in Test.objects.all():
    print(f"ID: {t.id}, Title: '{t.title}', Created: {t.created_at}, Attempts: {t.attempts.count()}")

print("\nAttempts per day:")
from django.db.models import Count
from django.db.models.functions import TruncDate

daily = TestAttempt.objects.annotate(date=TruncDate('submitted_at')).values('date').annotate(count=Count('id')).order_by('date')
for d in daily:
    print(f"Date: {d['date']}, Attempts: {d['count']}")

