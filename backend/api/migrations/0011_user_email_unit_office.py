from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0010_purchaserequest_source_filename'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='email',
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name='user',
            name='unit_office',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
