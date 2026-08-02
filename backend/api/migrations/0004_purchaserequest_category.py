from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0003_purchaserequest_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaserequest',
            name='category',
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
    ]
