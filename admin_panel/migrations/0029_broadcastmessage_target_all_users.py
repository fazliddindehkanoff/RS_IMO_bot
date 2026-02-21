# Generated manually for broadcast target_all_users filter

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0028_partner_student_partner'),
    ]

    operations = [
        migrations.AddField(
            model_name='broadcastmessage',
            name='target_all_users',
            field=models.BooleanField(
                default=False,
                help_text="Belgilanganda xabar barcha faol foydalanuvchilarga yuboriladi (boshqa filtrlar hisobga olinmaydi).",
                verbose_name="Barcha foydalanuvchilarga",
            ),
        ),
    ]
