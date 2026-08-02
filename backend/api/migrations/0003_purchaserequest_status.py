# Generated manually to add PR workflow status
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_purchaserequest_purchaserequestitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaserequest',
            name='status',
            field=models.CharField(
                choices=[
                    ('uploaded', 'Uploaded'),
                    ('in_review', 'In Review'),
                    ('matched', 'Matched'),
                    ('approved', 'Approved'),
                    ('rejected', 'Rejected'),
                ],
                default='uploaded',
                max_length=32,
            ),
        ),
    ]
