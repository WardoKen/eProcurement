from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0013_purchaserequest_submitted_by'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='notification_type',
            field=models.CharField(
                choices=[
                    ('opportunity', 'New Procurement Opportunity'),
                    ('rfq_received', 'New Request for Quotation'),
                    ('quotation_submitted', 'Quotation Submitted'),
                    ('quotation_review', 'Quotation Under Review'),
                    ('quotation_awarded', 'Quotation Awarded'),
                    ('quotation_rejected', 'Quotation Rejected'),
                    ('profile_approved', 'Profile Approved'),
                ],
                max_length=50,
            ),
        ),
        migrations.CreateModel(
            name='RFQ',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rfq_no', models.CharField(max_length=50, unique=True)),
                ('subject', models.CharField(max_length=255)),
                ('message', models.TextField()),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('sent', 'Sent'), ('quotation_received', 'Quotation Received'), ('completed', 'Completed')], default='draft', max_length=32)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_rfqs', to='api.user')),
                ('purchase_request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rfqs', to='api.purchaserequest')),
                ('supplier', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rfqs', to='api.supplier')),
            ],
        ),
    ]