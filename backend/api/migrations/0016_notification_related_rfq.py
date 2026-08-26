from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('api', '0015_quotation_rfq')]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='related_rfq_id',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]