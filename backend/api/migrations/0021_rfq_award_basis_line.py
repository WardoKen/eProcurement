# Rename the "By Unit" award basis to "By Line" (value 'UNIT' -> 'LINE').

from django.db import migrations, models


def unit_to_line(apps, schema_editor):
    RFQ = apps.get_model('api', 'RFQ')
    RFQ.objects.filter(award_basis='UNIT').update(award_basis='LINE')


def line_to_unit(apps, schema_editor):
    RFQ = apps.get_model('api', 'RFQ')
    RFQ.objects.filter(award_basis='LINE').update(award_basis='UNIT')


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0020_rfq_selection_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='rfq',
            name='award_basis',
            field=models.CharField(
                choices=[('LOT', 'By Lot'), ('LINE', 'By Line')],
                default='LOT',
                max_length=10,
            ),
        ),
        migrations.RunPython(unit_to_line, line_to_unit),
    ]
