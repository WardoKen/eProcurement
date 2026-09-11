# Rename the "award_basis" field to "quotation_basis" (terminology change only;
# values LOT/LINE and their labels are unchanged).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0024_rfq_category_alter_rfq_rfq_no_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='rfq',
            old_name='award_basis',
            new_name='quotation_basis',
        ),
        migrations.AlterField(
            model_name='rfq',
            name='quotation_basis',
            field=models.CharField(
                choices=[('LOT', 'By Lot'), ('LINE', 'By Line')],
                default='LOT',
                max_length=10,
            ),
        ),
    ]
