from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0005_purchaserequestitem_category'),
    ]

    operations = [
        migrations.CreateModel(
            name='Quotation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quoted_amount', models.DecimalField(decimal_places=2, max_digits=14)),
                ('estimated_delivery_days', models.IntegerField(blank=True, null=True)),
                ('warranty_months', models.IntegerField(blank=True, null=True)),
                ('remarks', models.TextField(blank=True)),
                ('attachment_filename', models.CharField(blank=True, max_length=512)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('submitted', 'Submitted'), ('under_review', 'Under Review'), ('awarded', 'Awarded'), ('rejected', 'Rejected')], default='draft', max_length=32)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('purchase_request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='quotations', to='api.purchaserequest')),
                ('supplier', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='quotations', to='api.supplier')),
            ],
        ),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(choices=[('opportunity', 'New Procurement Opportunity'), ('quotation_submitted', 'Quotation Submitted'), ('quotation_review', 'Quotation Under Review'), ('quotation_awarded', 'Quotation Awarded'), ('quotation_rejected', 'Quotation Rejected'), ('profile_approved', 'Profile Approved')], max_length=50)),
                ('title', models.CharField(max_length=255)),
                ('message', models.TextField()),
                ('is_read', models.BooleanField(default=False)),
                ('related_pr_id', models.IntegerField(blank=True, null=True)),
                ('related_quotation_id', models.IntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('supplier', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='api.supplier')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='quotation',
            constraint=models.UniqueConstraint(fields=('supplier', 'purchase_request'), name='unique_supplier_pr_quotation'),
        ),
    ]
