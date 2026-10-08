"""Cross-app, low-risk content automation hooks."""
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.html import strip_tags

from core.image_optimization import optimise_uploaded_image


_SEO_SOURCE_FIELDS = {'title', 'description', 'short_description', 'summary'}
_SEO_TARGET_FIELDS = {'meta_title', 'meta_description', 'summary'}


def _field_names(sender):
    return {field.name for field in sender._meta.fields}


def _plain_text(value, limit):
    if not value:
        return ''
    return ' '.join(strip_tags(str(value)).split())[:limit]


@receiver(pre_save, dispatch_uid='core.optimise_image_fields_before_storage')
def optimise_image_fields(sender, instance, raw=False, **kwargs):
    """Optimise every newly-uploaded ImageField before its storage backend saves it."""
    if raw or getattr(instance, '_skip_image_optimisation', False):
        return

    for field in sender._meta.fields:
        if not isinstance(field, models.ImageField):
            continue
        image_field = getattr(instance, field.name, None)
        if not image_field or getattr(image_field, '_committed', True):
            continue
        optimised = optimise_uploaded_image(image_field)
        if optimised is not None:
            # Assigning ContentFile lets Django's normal FileField pre_save path
            # store the result once, under the existing upload_to policy.
            setattr(instance, field.name, optimised)


@receiver(pre_save, dispatch_uid='core.populate_seo_fields_from_content')
def populate_seo_fields(sender, instance, raw=False, update_fields=None, **kwargs):
    """Fill empty editable SEO fields from real content, never overwrite an editor.

    This supports Product, Article and StaticPage without coupling those apps to
    each other. It intentionally does not invent keywords or canonical domains.
    """
    if raw:
        return

    model_fields = _field_names(sender)
    if 'title' not in model_fields:
        return
    if not model_fields.intersection(_SEO_TARGET_FIELDS):
        return

    if update_fields is not None:
        changed = set(update_fields)
        if not changed.intersection(_SEO_SOURCE_FIELDS | _SEO_TARGET_FIELDS):
            return

    title = _plain_text(getattr(instance, 'title', ''), 70)
    description_source = (
        getattr(instance, 'meta_description', '')
        or getattr(instance, 'summary', '')
        or getattr(instance, 'short_description', '')
        or getattr(instance, 'description', '')
        or title
    )
    description = _plain_text(description_source, 160)

    if 'meta_title' in model_fields and not getattr(instance, 'meta_title', ''):
        instance.meta_title = title
    if 'meta_description' in model_fields and not getattr(instance, 'meta_description', ''):
        instance.meta_description = description
    # StaticPage uses ``summary`` as its SEO description.
    if 'summary' in model_fields and not getattr(instance, 'summary', ''):
        instance.summary = description
