from django.apps import apps
from django.core.management.base import BaseCommand
from django.db.models import ImageField

from core.image_optimization import optimise_uploaded_image


class Command(BaseCommand):
    help = 'Optimise existing ImageField files. Dry-run by default; pass --apply to write changes.'

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument('--apply', action='store_true', help='Write optimised WebP files and remove replaced originals.')
        mode.add_argument('--dry-run', action='store_true', help='Inspect candidates only (the default).')
        parser.add_argument('--app', help='Only process models in one Django app label.')

    def handle(self, *args, **options):
        apply_changes = options['apply']
        selected_app = options.get('app')
        checked = candidates = changed = 0

        for model in apps.get_models():
            if selected_app and model._meta.app_label != selected_app:
                continue
            image_fields = [field for field in model._meta.fields if isinstance(field, ImageField)]
            if not image_fields:
                continue

            for field in image_fields:
                queryset = model._default_manager.exclude(**{f'{field.name}__isnull': True})
                for instance in queryset.iterator(chunk_size=100):
                    image = getattr(instance, field.name)
                    if not image or not image.name:
                        continue
                    checked += 1
                    try:
                        image.open('rb')
                        optimized = optimise_uploaded_image(image)
                    except OSError as exc:
                        self.stderr.write(f'Skipped {model._meta.label}#{instance.pk} {field.name}: {exc}')
                        continue
                    finally:
                        try:
                            image.close()
                        except (AttributeError, OSError):
                            pass

                    if optimized is None:
                        continue
                    candidates += 1
                    if not apply_changes:
                        continue

                    old_name = image.name
                    storage = image.storage
                    # The pre_save image hook is for new browser/admin uploads.
                    # This file was already optimised here, so avoid a second pass.
                    instance._skip_image_optimisation = True
                    setattr(instance, field.name, optimized)
                    instance.save(update_fields=[field.name])
                    new_name = getattr(instance, field.name).name
                    if old_name != new_name and storage.exists(old_name):
                        storage.delete(old_name)
                    changed += 1

        mode = 'applied' if apply_changes else 'dry-run; no files changed'
        self.stdout.write(
            self.style.SUCCESS(
                f'Image optimisation {mode}. Checked: {checked}, candidates: {candidates}, changed: {changed}.'
            )
        )
