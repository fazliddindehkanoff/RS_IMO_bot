# Generated manually for image upload and markdown

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0006_test_language_delete_testassignment'),
    ]

    operations = [
        migrations.AddField(
            model_name='testquestion',
            name='image',
            field=models.ImageField(
                blank=True,
                help_text="Agar rasm bo'lsa, savol matni rasm ostida caption sifatida yuboriladi.",
                null=True,
                upload_to='questions/',
                verbose_name='Savol rasmi',
            ),
        ),
        migrations.RemoveField(
            model_name='testquestion',
            name='image_file_id',
        ),
    ]
