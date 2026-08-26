from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0012_seed_default_roles'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaserequest',
            name='submitted_by',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
