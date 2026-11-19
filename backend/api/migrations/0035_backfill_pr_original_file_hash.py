"""Backfill ``original_file_hash`` for existing PRs whose document is on disk.

``original_extract_json`` is deliberately NOT backfilled: for PRs created
before change history existed, the extraction output was never stored and
any BAC edits overwrote the extracted values, so there is no trustworthy
original to record. It stays null and the change-history API reports
``original_available: false`` for those PRs.
"""
import hashlib
from pathlib import Path

from django.conf import settings
from django.db import migrations


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def backfill_hashes(apps, schema_editor):
    PurchaseRequest = apps.get_model('api', 'PurchaseRequest')
    uploads = Path(settings.BASE_DIR) / 'uploads'
    rows = (
        PurchaseRequest.objects
        .filter(original_file_hash='')
        .exclude(source_filename='')
        .values_list('id', 'source_filename')
    )
    for pr_id, filename in rows:
        path = uploads / Path(filename).name
        try:
            digest = _sha256(path)
        except OSError:
            continue
        # .update() bypasses the model's write-once save() guard, which is
        # fine here: the field is blank for every row this touches.
        PurchaseRequest.objects.filter(id=pr_id, original_file_hash='').update(original_file_hash=digest)


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0034_pr_change_history'),
    ]

    operations = [
        migrations.RunPython(backfill_hashes, migrations.RunPython.noop),
    ]
