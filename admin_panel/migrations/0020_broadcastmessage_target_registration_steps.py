# Generated manually for broadcast_target_registration_steps

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0019_alter_registrationsource_source_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='broadcastmessage',
            name='target_registration_steps',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Tanlangan bosqichlarda to'xtab qolgan o'quvchilarga yuborish. Bo'sh qoldirilsa, barcha bosqichlar hisobga olinmaydi (faqat sinf / to'liq ro'yxatdan o'tmagan filtrlari ishlatiladi).",
                verbose_name="Ro'yxatdan o'tish bosqichi bo'yicha",
            ),
        ),
    ]
