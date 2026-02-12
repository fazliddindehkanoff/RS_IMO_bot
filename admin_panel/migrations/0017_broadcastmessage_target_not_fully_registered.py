# Generated manually for broadcast target_not_fully_registered filter

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0016_student_phone_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='broadcastmessage',
            name='target_not_fully_registered',
            field=models.BooleanField(
                default=False,
                help_text="Belgilanganda xabar faqat to'liq ro'yxatdan o'tmagan o'quvchilarga yuboriladi (ota-ona va o'qituvchi telefonlari bo'yicha).",
                verbose_name="Faqat to'liq ro'yxatdan o'tmaganlarga",
            ),
        ),
    ]
