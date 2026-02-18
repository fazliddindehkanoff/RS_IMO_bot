# Generated manually for Student.state (registration step synced from bot)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0021_student_referrer'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='state',
            field=models.CharField(
                blank=True,
                help_text="Foydalanuvchi qaysi qadamda ekanligi (bot tomonidan avtomatik yangilanadi)",
                max_length=100,
                null=True,
                verbose_name="Ro'yxatdan o'tish holati",
            ),
        ),
    ]
