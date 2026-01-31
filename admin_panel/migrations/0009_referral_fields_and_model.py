# Generated manually for referral functionality

from django.db import migrations, models
import django.db.models.deletion


def set_referral_codes(apps, schema_editor):
    """Set referral_code = str(telegram_id) for existing students."""
    Student = apps.get_model('admin_panel', 'Student')
    for s in Student.objects.filter(referral_code__isnull=True):
        s.referral_code = str(s.telegram_id)
        s.save(update_fields=['referral_code'])


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0008_remove_testquestion_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='referral_code',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Do'stlarni taklif qilish havolasida ishlatiladi (admin tomonidan tahrirlanmaydi)",
                max_length=64,
                null=True,
                unique=True,
                verbose_name='Referral kodi',
            ),
        ),
        migrations.AddField(
            model_name='student',
            name='referral_points',
            field=models.IntegerField(
                default=0,
                help_text="Har bir taklif qilingan do'st uchun 5 ball (admin tomonidan tahrirlanmaydi)",
                verbose_name='Referral ballari',
            ),
        ),
        migrations.CreateModel(
            name='Referral',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('points_earned', models.IntegerField(default=5, verbose_name='Olingan ball')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")),
                ('referrer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='referrals_made', to='admin_panel.student', verbose_name='Taklif qiluvchi')),
                ('referred', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='referred_by', to='admin_panel.student', verbose_name="Ro'yxatdan o'tgan")),
            ],
            options={
                'verbose_name': 'Referral',
                'verbose_name_plural': 'Referrallar',
                'db_table': 'referrals',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='referral',
            index=models.Index(fields=['referrer'], name='referrals_referre_idx'),
        ),
        migrations.AddIndex(
            model_name='referral',
            index=models.Index(fields=['created_at'], name='referrals_created_idx'),
        ),
        migrations.RunPython(set_referral_codes, migrations.RunPython.noop),
    ]
