"""Admin pages must stay well-formed HTML.

Django prints help texts and fieldset descriptions as raw HTML.  A help text
that merely *mentioned* «<style>» and «<script>» opened real elements in the
browser, and everything after it — the product file section, the image
inline and the save buttons — was swallowed as CSS text.  The test client
could not see it (the bytes were all there), so these tests parse the pages
the way a browser does.
"""
import re
from html.parser import HTMLParser

from django.apps import apps
from django.contrib import admin
from django.contrib.auth.models import User
from django.test import TestCase

from blog.models import Article
from pages.models import StaticPage
from product.models import Product, ProductCategory

# Elements whose content the HTML parser treats as raw text: one stray opening
# tag hides the rest of the document.
RAW_TEXT_TAG = re.compile(r'<\s*(script|style|textarea|title|noscript|template|iframe|xmp|plaintext)\b', re.I)


class _ElementCollector(HTMLParser):
    """Collects the start tags a browser would really create."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.submit_names = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.add(attrs['id'])
        if tag == 'input' and attrs.get('type') == 'submit' and attrs.get('name'):
            self.submit_names.add(attrs['name'])


def _parse(html):
    parser = _ElementCollector()
    parser.feed(html)
    parser.close()
    return parser


class AdminHelpTextTests(TestCase):
    def test_no_help_text_or_description_opens_a_raw_text_element(self):
        offenders = []
        for model in apps.get_models():
            for field in model._meta.get_fields():
                text = str(getattr(field, 'help_text', '') or '')
                if RAW_TEXT_TAG.search(text):
                    offenders.append(f'{model._meta.label}.{field.name} help_text')
        for model, model_admin in admin.site._registry.items():
            admins = [model_admin] + [inline(model, admin.site) for inline in model_admin.inlines]
            for item in admins:
                for name, options in (getattr(item, 'fieldsets', None) or ()):
                    if RAW_TEXT_TAG.search(str(options.get('description', '') or '')):
                        offenders.append(f'{type(item).__name__} fieldset «{name}» description')
                form = getattr(item, 'form', None)
                for field_name, field in getattr(form, 'base_fields', {}).items():
                    if RAW_TEXT_TAG.search(str(field.help_text or '')):
                        offenders.append(f'{type(item).__name__}.{field_name} form help_text')
        self.assertEqual(offenders, [], 'Write tag names without < > in admin texts: ' + '; '.join(offenders))


class AdminFormsRenderCompletelyTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('html-admin', 'h@example.com', 'Safe-pass-123!')
        self.client.force_login(self.admin)
        category = ProductCategory.objects.create(title='قالب', slug='tpl')
        self.product = Product.objects.create(vendor=self.admin, title='محصول', slug='p', description='x', price=1)
        self.product.category.add(category)
        self.page = StaticPage.objects.create(title='درباره', slug='about-x', content='x')
        self.article = Article.objects.filter().first()

    def _assert_complete(self, url, inline_ids=()):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        parsed = _parse(response.content.decode())
        self.assertIn('_save', parsed.submit_names, f'{url}: the save button is not a real element')
        for inline_id in inline_ids:
            self.assertIn(inline_id, parsed.ids, f'{url}: «{inline_id}» is swallowed')

    def test_product_forms_show_the_file_section_and_save_buttons(self):
        for url in ('/admin/product/product/add/', f'/admin/product/product/{self.product.pk}/change/'):
            self._assert_complete(url, inline_ids=('digital_asset-group', 'product_images-group'))

    def test_static_page_and_html_block_forms_render_completely(self):
        self._assert_complete('/admin/pages/staticpage/add/')
        self._assert_complete(f'/admin/pages/staticpage/{self.page.pk}/change/')
        self._assert_complete('/admin/core/htmlblock/add/')

    def test_article_form_renders_completely(self):
        self._assert_complete('/admin/blog/article/add/')
