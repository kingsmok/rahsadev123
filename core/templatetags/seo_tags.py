# -*- coding: utf-8 -*-
"""تگ‌های سئو — ساخت خودکار اسکیمای JSON-LD برای همه بخش‌های سایت.

هر تگ یک بلاک <script type="application/ld+json"> کامل و معتبر تولید می‌کند
تا موتورهای جست‌وجو و دستیارهای هوش مصنوعی محتوای سایت را دقیق درک کنند.
"""
import json

from django import template
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe

from core.models import SiteSettings

register = template.Library()


# JSON-LD is placed inside a <script> element.  Escaping these characters is
# required even though ``json.dumps`` has serialized the value: a stored title
# such as ``</script><script>…`` would otherwise close the JSON-LD element.
_JSON_SCRIPT_ESCAPE = str.maketrans({
    '<': chr(92) + 'u003C',
    '>': chr(92) + 'u003E',
    '&': chr(92) + 'u0026',
    chr(0x2028): chr(92) + 'u2028',
    chr(0x2029): chr(92) + 'u2029',
})


def _json(data):
    """Return compact, script-element-safe JSON-LD without changing its data."""
    return json.dumps(data, ensure_ascii=False, separators=(',', ':')).translate(_JSON_SCRIPT_ESCAPE)


def _script(data):
    return mark_safe(
        '<script type="application/ld+json">%s</script>' % _json(data)
    )


def _absolute(context, path):
    """مسیر نسبی → آدرس مطلق با scheme و host درخواست."""
    request = context.get('request')
    if request is None:
        return path
    return request.build_absolute_uri(path)


def _settings(context=None):
    """Prefer the already-loaded global template setting over another query."""
    if context is not None:
        marker = object()
        value = context.get('site_settings', marker)
        if value is not marker:
            return value
    return SiteSettings.objects.first()


def _site_logo(context, settings_obj):
    """Use the configured brand logo when available, otherwise a stable fallback."""
    if settings_obj and settings_obj.logo:
        return _absolute(context, settings_obj.logo.url)
    return _absolute(context, '/static/img/favicon.png')


def _clean(text, limit=300):
    """حذف تگ‌های HTML و کوتاه‌سازی امن متن برای اسکیما."""
    if not text:
        return ''
    return strip_tags(str(text)).strip()[:limit]


@register.simple_tag(takes_context=True)
def organization_schema(context):
    """سازمان/ کسب‌وکار — در همه صفحات."""
    s = _settings(context)
    site_name = s.site_name if s else 'فایل‌مارکت'
    data = {
        '@context': 'https://schema.org',
        '@type': 'Organization',
        'name': site_name,
        'url': _absolute(context, '/'),
        'logo': _site_logo(context, s),
    }
    if s:
        same_as = [link for link in [
            s.instagram_link, s.telegram_link, s.whatsapp_link, s.twitter_link,
            s.youtube_link, s.linkedin_link,
        ] if link]
        if same_as:
            data['sameAs'] = same_as
        contact = {}
        if s.phone1:
            contact['telephone'] = s.phone1
        if s.email1:
            contact['email'] = s.email1
        if s.address:
            contact['address'] = {
                '@type': 'PostalAddress',
                'addressLocality': s.address,
                'addressCountry': 'IR',
            }
        if contact:
            contact['@type'] = 'ContactPoint'
            contact['contactType'] = 'customer support'
            contact['availableLanguage'] = ['fa']
            data['contactPoint'] = contact
    return _script(data)


@register.simple_tag(takes_context=True)
def website_schema(context):
    """وب‌سایت با اکشن جست‌وجو (SearchAction) — در همه صفحات."""
    s = _settings(context)
    site_name = s.site_name if s else 'فایل‌مارکت'
    data = {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        'name': site_name,
        'url': _absolute(context, '/'),
        'inLanguage': 'fa-IR',
        'potentialAction': {
            '@type': 'SearchAction',
            'target': {
                '@type': 'EntryPoint',
                'urlTemplate': _absolute(context, '/products/product_search/?search={search_term_string}'),
            },
            'query-input': 'required name=search_term_string',
        },
    }
    return _script(data)


@register.simple_tag(takes_context=True)
def webpage_schema(context):
    """Create a truthful WebPage/ItemPage graph for every indexable page.

    Detail views already add richer Product or BlogPosting entities. This common
    layer connects those entities to a stable canonical URL without publishing
    a schema graph for private, transactional or noindex routes.
    """
    if str(context.get('meta_robots', '')).startswith('noindex'):
        return ''

    request = context.get('request')
    if request is None:
        return ''

    settings_obj = _settings(context)
    site_name = context.get('site_name') or (settings_obj.site_name if settings_obj else 'فایل‌مارکت')
    entity = next(
        (
            context.get(key)
            for key in ('products', 'product', 'article', 'page', 'category', 'brand')
            if getattr(context.get(key), 'title', None)
        ),
        None,
    )
    resolver = getattr(request, 'resolver_match', None)
    resolver_name = getattr(resolver, 'url_name', '') or ''
    is_collection = resolver_name.endswith('_list') or resolver_name in {
        'category_product_list', 'brand_product_list', 'discount_product', 'article_category',
    }
    page_type = 'ItemPage' if entity and not is_collection else ('CollectionPage' if is_collection else 'WebPage')

    title = _clean(
        getattr(entity, 'meta_title', '') or getattr(entity, 'title', '') or site_name,
        110,
    )
    description = _clean(
        getattr(entity, 'meta_description', '')
        or getattr(entity, 'summary', '')
        or getattr(entity, 'short_description', '')
        or getattr(entity, 'description', '')
        or (settings_obj.default_meta_description if settings_obj else ''),
        300,
    )
    canonical = getattr(entity, 'canonical_url', '') or context.get('canonical_url') or request.build_absolute_uri(request.path)
    data = {
        '@context': 'https://schema.org',
        '@type': page_type,
        'name': title,
        'url': canonical,
        'inLanguage': 'fa-IR',
        'isPartOf': {'@type': 'WebSite', 'name': site_name, 'url': _absolute(context, '/')},
    }
    if description:
        data['description'] = description
    image = getattr(entity, 'image', None)
    if image:
        data['primaryImageOfPage'] = {
            '@type': 'ImageObject',
            'url': _absolute(context, image.url),
        }
    modified = getattr(entity, 'updated_at', None)
    if modified:
        data['dateModified'] = modified.isoformat()
    return _script(data)


@register.simple_tag(takes_context=True)
def breadcrumb_schema(context, items):
    """مسیر راهنما (BreadcrumbList).

    items: لیست (عنوان، مسیر) — مسیر None یعنی صفحه فعلی.
    """
    crumbs = []
    for i, entry in enumerate(items, start=1):
        name, path = entry[0], entry[1]
        crumb = {'@type': 'ListItem', 'position': i, 'name': str(name)}
        if path:
            crumb['item'] = _absolute(context, str(path))
        crumbs.append(crumb)
    return _script({
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        'itemListElement': crumbs,
    })


def _crumbs(context, entries):
    """ساخت BreadcrumbList از لیست (عنوان، مسیر | None)."""
    return breadcrumb_schema(context, entries)


@register.simple_tag(takes_context=True)
def product_breadcrumb(context, product):
    """مسیر: خانه ← فروشگاه ← دسته‌بندی ← محصول."""
    entries = [('خانه', '/'), ('فروشگاه', '/products/')]
    cat = product.category.first()
    if cat:
        entries.append((cat.title, '/products/category/%s/' % cat.slug))
    entries.append((product.title, None))
    return _crumbs(context, entries)


@register.simple_tag(takes_context=True)
def category_breadcrumb(context, category):
    entries = [('خانه', '/'), ('فروشگاه', '/products/'), (category.title, None)]
    return _crumbs(context, entries)


@register.simple_tag(takes_context=True)
def brand_breadcrumb(context, brand):
    entries = [('خانه', '/'), ('فروشگاه', '/products/'), (brand.title, None)]
    return _crumbs(context, entries)


@register.simple_tag(takes_context=True)
def store_breadcrumb(context, label=None):
    entries = [('خانه', '/'), (label or 'فروشگاه', None)]
    return _crumbs(context, entries)


@register.simple_tag(takes_context=True)
def article_breadcrumb(context, article):
    entries = [('خانه', '/'), ('وبلاگ', '/blog/')]
    cat = article.category.first()
    if cat:
        entries.append((cat.title, '/blog/category/%s/' % cat.slug))
    entries.append((article.title, None))
    return _crumbs(context, entries)


@register.simple_tag(takes_context=True)
def blog_breadcrumb(context, label=None):
    entries = [('خانه', '/'), (label or 'وبلاگ', None)]
    return _crumbs(context, entries)


@register.simple_tag(takes_context=True)
def page_breadcrumb(context, title):
    entries = [('خانه', '/'), (title, None)]
    return _crumbs(context, entries)


@register.simple_tag(takes_context=True)
def product_schema(context, product):
    """محصول دیجیتال — قیمت، موجودی، برند، دسته‌بندی و تصویر."""
    url = _absolute(context, '/products/%s/%s/' % (product.pid, product.slug))
    data = {
        '@context': 'https://schema.org',
        '@type': 'Product',
        'name': product.title,
        'url': url,
        'sku': str(product.pid),
        'description': _clean(
            product.meta_description or product.short_description or product.description, 500
        ) or product.title,
    }
    if getattr(product, 'image', None) and product.image:
        data['image'] = [_absolute(context, product.image.url)]
    brands = list(product.brand.all()[:3])
    if brands:
        data['brand'] = [{'@type': 'Brand', 'name': b.title} for b in brands]
    categories = list(product.category.all()[:3])
    if categories:
        data['category'] = ' > '.join(c.title for c in categories)
    if getattr(product, 'demo_url', None):
        data['additionalProperty'] = [{
            '@type': 'PropertyValue',
            'name': 'demoUrl',
            'value': product.demo_url,
        }]
    offer = {
        '@type': 'Offer',
        'url': url,
        'priceCurrency': 'IRR',
        'price': str(product.price * 10),  # model/UI amounts are تومان; Schema uses IRR.
        'availability': 'https://schema.org/InStock' if product.is_available else 'https://schema.org/OutOfStock',
        'itemCondition': 'https://schema.org/NewCondition',
        'seller': {'@type': 'Organization', 'name': (context.get('site_name') or 'فایل‌مارکت')},
    }
    # ``old_price`` is a visual crossed-out amount, not a second current offer;
    # publishing it as PriceSpecification would make the structured data
    # ambiguous. The current purchasable price above is the only offer emitted.
    data['offers'] = offer
    return _script(data)


@register.simple_tag(takes_context=True)
def item_list_schema(context, products):
    """فهرست محصولات صفحه‌بندی‌شده (فقط صفحه اول ایندکس می‌شود).

    products می‌تواند QuerySet، لیست یا Page صفحه‌بندی جنگو باشد.
    """
    # اگر Page است و صفحه اول نیستیم، اسکیما خروجی نده (محتوای تکراری)
    if hasattr(products, 'number') and getattr(products, 'number', 1) != 1:
        return ''
    try:
        items = []
        for i, p in enumerate(list(products)[:12], start=1):
            items.append({
                '@type': 'ListItem',
                'position': i,
                'url': _absolute(context, '/products/%s/%s/' % (p.pid, p.slug)),
                'name': p.title,
            })
    except TypeError:
        return ''
    if not items:
        return ''
    return _script({
        '@context': 'https://schema.org',
        '@type': 'ItemList',
        'itemListElement': items,
    })


@register.simple_tag(takes_context=True)
def article_list_schema(context, articles):
    """ItemList for the first page of public articles."""
    if hasattr(articles, 'number') and getattr(articles, 'number', 1) != 1:
        return ''
    try:
        items = [
            {
                '@type': 'ListItem',
                'position': index,
                'url': _absolute(context, '/blog/%s/' % article.slug),
                'name': article.title,
            }
            for index, article in enumerate(list(articles)[:12], start=1)
        ]
    except TypeError:
        return ''
    if not items:
        return ''
    return _script({
        '@context': 'https://schema.org',
        '@type': 'ItemList',
        'itemListElement': items,
    })


@register.simple_tag(takes_context=True)
def article_schema(context, article):
    """مقاله وبلاگ (BlogPosting) با نویسنده و ناشر."""
    data = {
        '@context': 'https://schema.org',
        '@type': 'BlogPosting',
        'headline': article.title[:110],
        'description': _clean(
            article.meta_description or article.description, 300
        ) or article.title,
        'inLanguage': 'fa-IR',
        'datePublished': article.created_at.strftime('%Y-%m-%dT%H:%M:%S+03:30'),
        'dateModified': article.updated_at.strftime('%Y-%m-%dT%H:%M:%S+03:30'),
        'mainEntityOfPage': {
            '@type': 'WebPage',
            '@id': _absolute(context, '/blog/%s/' % article.slug),
        },
        'author': {
            '@type': 'Person',
            'name': article.author.get_full_name() or article.author.username,
        },
        'publisher': {
            '@type': 'Organization',
            'name': (context.get('site_name') or 'فایل‌مارکت'),
            'logo': {'@type': 'ImageObject', 'url': _site_logo(context, _settings(context))},
        },
    }
    if getattr(article, 'image', None) and article.image:
        data['image'] = [_absolute(context, article.image.url)]
    return _script(data)


@register.simple_tag(takes_context=True)
def faq_schema(context, faq_pairs):
    """سوالات متداول (FAQPage) — faq_pairs: لیست (پرسش، پاسخ)."""
    if not faq_pairs:
        return ''
    return _script({
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        'mainEntity': [
            {
                '@type': 'Question',
                'name': _clean(q, 200),
                'acceptedAnswer': {'@type': 'Answer', 'text': _clean(a, 800)},
            }
            for q, a in faq_pairs
            if _clean(q) and _clean(a)
        ],
    })


@register.simple_tag(takes_context=True)
def faq_schema_from_html(context, html):
    """استخراج خودکار پرسش/پاسخ از محتوای صفحه سوالات متداول (h3 + p)."""
    import re
    if not html:
        return ''
    pairs = re.findall(
        r'<h3[^>]*>(.*?)</h3>\s*<p[^>]*>(.*?)</p>',
        strip_scripts(html), flags=re.DOTALL,
    )
    clean_pairs = [(strip_tags(q).strip(), strip_tags(a).strip()) for q, a in pairs]
    clean_pairs = [(q, a) for q, a in clean_pairs if q and a]
    return faq_schema(context, clean_pairs)


def strip_scripts(html):
    """حذف تگ‌های اسکریپت/استایل قبل از تحلیل."""
    import re
    html = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', str(html), flags=re.DOTALL | re.IGNORECASE)
    return html


@register.simple_tag(takes_context=True)
def contact_page_schema(context):
    """صفحه تماس با ما + اطلاعات تماس سازمان."""
    s = _settings(context)
    data = {
        '@context': 'https://schema.org',
        '@type': 'ContactPage',
        'url': _absolute(context, '/contact/'),
        'inLanguage': 'fa-IR',
    }
    if s:
        cp = {'@type': 'ContactPoint', 'contactType': 'customer support', 'availableLanguage': ['fa']}
        if s.phone1:
            cp['telephone'] = s.phone1
        if s.email1:
            cp['email'] = s.email1
        data['mainEntity'] = {
            '@type': 'Organization',
            'name': s.site_name,
            'url': _absolute(context, '/'),
            'contactPoint': cp,
        }
    return _script(data)


@register.simple_tag(takes_context=True)
def service_schema(context, packages):
    """فهرست خدمات طراحی وب با تعرفه‌ها (Service + Offer)."""
    offers = []
    for p in packages[:10]:
        offer = {
            '@type': 'Offer',
            'name': p.title,
            'description': _clean(getattr(p, 'short_description', '') or p.title, 300),
        }
        # ServicePackage prices, like product prices, are stored and displayed
        # in تومان. schema.org's IRR currency value must therefore be ریال.
        # A consultation-only package has no price and must not publish "None".
        if p.price is not None:
            offer['price'] = str(p.price * 10)
            offer['priceCurrency'] = 'IRR'
        if getattr(p, 'delivery_days', None):
            offer['deliveryLeadTime'] = {
                '@type': 'QuantitativeValue', 'value': int(p.delivery_days), 'unitCode': 'DAY',
            }
        offers.append(offer)
    data = {
        '@context': 'https://schema.org',
        '@type': 'Service',
        'serviceType': 'Web Design & Development',
        'name': 'خدمات طراحی وب سایت',
        'provider': {
            '@type': 'Organization',
            'name': (context.get('site_name') or 'فایل‌مارکت'),
            'url': _absolute(context, '/'),
        },
        'areaServed': 'IR',
        'availableLanguage': ['fa'],
    }
    if offers:
        data['hasOfferCatalog'] = {
            '@type': 'OfferCatalog',
            'name': 'تعرفه‌های طراحی وب سایت',
            'itemListElement': offers,
        }
    return _script(data)
