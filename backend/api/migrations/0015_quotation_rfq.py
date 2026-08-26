from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('api', '0014_rfq_notification_type')]

    operations = [
        migrations.AddField(
            model_name='quotation',
            name='rfq',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='quotations', to='api.rfq'),
        ),
    ]