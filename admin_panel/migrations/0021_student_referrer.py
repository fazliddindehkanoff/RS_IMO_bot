# Generated manually for persistent referral storage

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0020_broadcastmessage_target_registration_steps'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='referrer',
            field=models.ForeignKey(
                blank=True,
                help_text="Bu foydalanuvchi qaysi student havolasi orqali kelgan (DB da saqlanadi)",
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name='referred_students',
                to='admin_panel.student',
                verbose_name='Taklif qiluvchi',
            ),
        ),
    ]
