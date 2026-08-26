from django.db import migrations


DEFAULT_ROLES = [
    ('admin', 'BAC administrator'),
    ('buyer', 'Buyer or end user'),
    ('supplier', 'Registered supplier'),
]


def seed_default_roles(apps, schema_editor):
    role_model = apps.get_model('api', 'Role')
    for name, description in DEFAULT_ROLES:
        role_model.objects.get_or_create(name=name, defaults={'description': description})


def remove_seeded_roles(apps, schema_editor):
    role_model = apps.get_model('api', 'Role')
    role_model.objects.filter(name__in=['admin', 'buyer']).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0011_user_email_unit_office'),
    ]

    operations = [
        migrations.RunPython(seed_default_roles, remove_seeded_roles),
    ]
