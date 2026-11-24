# Evaluation and award are out of eProcure's scope: drop the "awarded"
# quotation status and the "Quotation Awarded" notification type. Nothing in
# the app ever set them; any such rows are moved to supported values first.

from django.db import migrations, models


def clear_award_rows(apps, schema_editor):
    Quotation = apps.get_model('api', 'Quotation')
    Notification = apps.get_model('api', 'Notification')
    # The quotation was submitted before it could be awarded.
    Quotation.objects.filter(status='awarded').update(status='submitted')
    Notification.objects.filter(notification_type='quotation_awarded').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0038_explicit_pr_posting'),
    ]

    operations = [
        migrations.RunPython(clear_award_rows, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='notification',
            name='notification_type',
            field=models.CharField(choices=[('opportunity', 'New Procurement Opportunity'), ('rfq_received', 'New Request for Quotation'), ('quotation_submitted', 'Quotation Submitted'), ('quotation_review', 'Quotation Under Review'), ('quotation_rejected', 'Quotation Rejected'), ('profile_approved', 'Profile Approved')], max_length=50),
        ),
        migrations.AlterField(
            model_name='quotation',
            name='status',
            field=models.CharField(choices=[('draft', 'Draft'), ('submitted', 'Submitted'), ('under_review', 'Under Review'), ('rejected', 'Rejected')], default='draft', max_length=32),
        ),
    ]
