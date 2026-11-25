# What the signature detector saw when the End User submitted the PR, so the
# BAC's PR list can flag the boxes it still has to verify by hand.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0039_remove_award_choices'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaserequest',
            name='signature_check',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
