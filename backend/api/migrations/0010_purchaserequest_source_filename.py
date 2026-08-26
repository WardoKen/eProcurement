from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0009_prnumbersequence_purchase_request_pr_no_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaserequest',
            name='source_filename',
            field=models.CharField(blank=True, max_length=512),
        ),
    ]
