# Generated for manual BAC supplier selection audit trail.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0019_rfq_submitted_at_rfq_submitted_pdf'),
    ]

    operations = [
        migrations.AddField(
            model_name='rfq',
            name='selection_type',
            field=models.CharField(
                choices=[
                    ('category_match', 'Category Match'),
                    ('manual_bac', 'Manual BAC Selection'),
                ],
                default='category_match',
                max_length=32,
            ),
        ),
    ]
