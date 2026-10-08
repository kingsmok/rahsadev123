"""Storage adapters for public, non-paid uploads."""
from pathlib import PurePath

from django.core.files.storage import FileSystemStorage

from core.image_optimization import optimise_uploaded_image


class CkeditorImageStorage(FileSystemStorage):
    """Keep rich-text image uploads public but validate/optimise them consistently."""

    def _save(self, name, content):
        optimised = optimise_uploaded_image(content)
        safe_name = PurePath(name).name or 'image'
        if optimised is not None:
            content = optimised
            safe_name = optimised.name
        return super()._save(f'ckeditor-images/{safe_name}', content)
