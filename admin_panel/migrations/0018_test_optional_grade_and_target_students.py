# Generated for Test: optional grade and target_students M2M

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0017_broadcastmessage_target_not_fully_registered'),
    ]

    operations = [
        migrations.AlterField(
            model_name='test',
            name='grade',
            field=models.IntegerField(
                blank=True,
                choices=[(5, '5-sinf'), (6, '6-sinf'), (7, '7-sinf'), (8, '8-sinf')],
                help_text="Ixtiyoriy. Bo'sh qoldirsangiz, testni faqat tanlangan o'quvchilarga yuborishingiz mumkin.",
                null=True,
                verbose_name='Sinf',
            ),
        ),
        migrations.AddField(
            model_name='test',
            name='target_students',
            field=models.ManyToManyField(
                blank=True,
                help_text="Sinf bo'sh bo'lsa, test shu o'quvchilarga yuboriladi.",
                related_name='targeted_tests',
                to='admin_panel.student',
                verbose_name="Tanlangan o'quvchilar",
            ),
        ),
    ]
