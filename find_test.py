import csv
from admin_panel.models import Test
for t in Test.objects.all():
    print(f"ID: {t.id}, Title: {t.title}, Created: {t.created_at}")
