from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from product.models import DigitalAsset
from product.storage import PrivateDigitalStorage


class Command(BaseCommand):
    help = 'Copy legacy public digital-products files to private storage. Dry-run by default.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Copy files into PRIVATE_MEDIA_ROOT.')
        parser.add_argument(
            '--delete-public',
            action='store_true',
            help='After a verified copy, remove each legacy public file. Requires --apply.',
        )

    def handle(self, *args, **options):
        apply_changes = options['apply']
        delete_public = options['delete_public']
        if delete_public and not apply_changes:
            raise CommandError('--delete-public requires --apply.')

        storage = PrivateDigitalStorage()
        inspected = copied = already_private = missing = deleted = 0
        for asset in DigitalAsset.objects.exclude(file='').iterator(chunk_size=100):
            name = asset.file.name
            legacy_path = Path(settings.MEDIA_ROOT) / name
            private_path = Path(settings.PRIVATE_MEDIA_ROOT) / name
            inspected += 1

            if private_path.is_file():
                already_private += 1
                if delete_public and legacy_path.is_file() and apply_changes:
                    legacy_path.unlink()
                    deleted += 1
                continue
            if not legacy_path.is_file():
                missing += 1
                self.stderr.write(f'Missing legacy file for DigitalAsset#{asset.pk}: {name}')
                continue
            if not apply_changes:
                self.stdout.write(f'Would copy: {name}')
                continue

            with legacy_path.open('rb') as source:
                stored_name = storage.save(name, File(source, name=name))
            stored_path = Path(settings.PRIVATE_MEDIA_ROOT) / stored_name
            if stored_name != name or not stored_path.is_file() or stored_path.stat().st_size != legacy_path.stat().st_size:
                raise RuntimeError(f'Private copy verification failed for {name}')
            copied += 1
            if delete_public:
                legacy_path.unlink()
                deleted += 1

        mode = 'applied' if apply_changes else 'dry-run; no files copied'
        self.stdout.write(self.style.SUCCESS(
            f'Private-asset migration {mode}. Inspected: {inspected}, copied: {copied}, '
            f'already private: {already_private}, missing: {missing}, legacy deleted: {deleted}.'
        ))
