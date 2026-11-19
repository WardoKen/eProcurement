"""Create or reset the local test accounts (see TEST_ACCOUNTS.md).

    python manage.py seed_test_accounts

Each account's password is its username. Re-running resets the passwords
and reactivates the accounts; nothing else about existing records changes.
The supplier account is linked to a Supplier the same way login links one
(the supplier's email contains the username, or its contact person equals
the account's full name). If no supplier links yet, an approved demo
supplier with verified documents is created so the portal is usable.

Refuses to run when DEBUG is off, so these weak passwords never reach a
production database by accident.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models import Category, Role, Supplier, SupplierCategory, SupplierDocument, User
from api.supplier_registration import REQUIRED_UPLOAD_KEYS, get_required_business_document_key
from api.views import hash_password

TEST_ACCOUNTS = [
    # (username, role, full name, email)
    ('admintest', 'admin', 'BAC Secretariat (test)', ''),
    ('endusertest', 'buyer', 'End User (test)', ''),
    ('emailtest', 'supplier', 'emailtest', 'emailtest@demo-vendors.test'),
]

DEMO_SUPPLIER_CATEGORIES = ['Advertising Agency Services', 'Janitorial Supplies']
DEMO_DOCUMENT_FILE = 'seed_demo_eligibility_document.pdf'


class Command(BaseCommand):
    help = 'Create or reset the local test accounts; each password is its username.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--allow-without-debug', action='store_true',
            help='Run even when DEBUG is off (do not use on production).',
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options['allow_without_debug']:
            raise CommandError('DEBUG is off. Test accounts with weak passwords are for local development only.')

        with transaction.atomic():
            for username, role_name, full_name, email in TEST_ACCOUNTS:
                role, _ = Role.objects.get_or_create(name=role_name)
                user = User.objects.filter(username=username).first()
                created = user is None
                if created:
                    user = User(username=username, role=role, full_name=full_name, email=email)
                elif user.role_id != role.id:
                    raise CommandError(f'{username} exists with role "{user.role.name}", expected "{role_name}". Not changed.')
                user.password_hash = hash_password(username)
                user.is_active = True
                user.save()
                self.stdout.write(f'{"Created" if created else "Reset"} {role_name} account {username}')

                if role_name == 'supplier':
                    self._ensure_supplier(user)

        self.stdout.write(self.style.SUCCESS('Test accounts ready. Each password is the same as its username.'))

    def _ensure_supplier(self, user):
        supplier = Supplier.objects.filter(email__icontains=user.username).order_by('-created_at').first()
        if supplier is None and user.full_name:
            supplier = Supplier.objects.filter(contact_person__iexact=user.full_name.strip()).order_by('-created_at').first()
        if supplier is not None:
            self.stdout.write(f'  linked to supplier #{supplier.id} {supplier.company_name} ({supplier.status})')
            return

        supplier = Supplier.objects.create(
            company_name='Emailtest Demo Trading',
            business_type='Corporation',
            business_address='Tuburan, Cebu',
            contact_person=user.full_name or user.username,
            email=user.email or f'{user.username}@demo-vendors.test',
            products_services='Demo supplier for local testing.',
            status='Approved',
        )
        for name in DEMO_SUPPLIER_CATEGORIES:
            category = Category.objects.filter(name=name).first()
            if category:
                SupplierCategory.objects.get_or_create(supplier=supplier, category=category)
        doc_keys = list(REQUIRED_UPLOAD_KEYS)
        business_key = get_required_business_document_key(supplier.business_type)
        if business_key:
            doc_keys.append(business_key)
        for key in doc_keys:
            SupplierDocument.objects.create(
                supplier=supplier, doc_type=key, filename=DEMO_DOCUMENT_FILE,
                original_name=f'{key}.pdf', verification_status='Verified',
            )
        self.stdout.write(f'  created approved supplier #{supplier.id} {supplier.company_name}')
