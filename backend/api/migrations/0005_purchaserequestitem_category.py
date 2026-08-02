from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0004_purchaserequest_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaserequestitem',
            name='category',
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
    ]
