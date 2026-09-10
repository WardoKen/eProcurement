# Records the Buyer's acknowledgement of the PR Submission Declaration.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0021_rfq_award_basis_line'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaserequest',
            name='declaration_acknowledged',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='purchaserequest',
            name='declaration_acknowledged_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
