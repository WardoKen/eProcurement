from django.db import migrations, models


def create_sequence_lock(apps, schema_editor):
    sequence_model = apps.get_model('api', 'PRNumberSequence')
    sequence_model.objects.get_or_create(key='global')


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0008_supplier_review_remarks_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PRNumberSequence',
            fields=[
                ('key', models.CharField(default='global', max_length=20, primary_key=True, serialize=False)),
            ],
        ),
        migrations.AlterField(
            model_name='purchaserequest',
            name='pr_no',
            field=models.CharField(blank=True, max_length=50, null=True, unique=True),
        ),
        migrations.RunPython(create_sequence_lock, migrations.RunPython.noop),
    ]
