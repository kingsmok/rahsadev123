"""Dark mode: the night stylesheet must never leak into the day theme, and the
pages that do not extend base.html (offline, emergency 500) follow the choice."""
import re
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from core.models import SiteSettings
from core.tests_features import PNG

CSS_DIR = Path(settings.BASE_DIR) / 'static' / 'css'


def _split_top_level(selector_list):
    """Split «a, b:is(c, d)» on top-level commas only."""
    parts, depth, current = [], 0, ''
    for char in selector_list:
        if char in '([':
            depth += 1
        elif char in ')]':
            depth -= 1
        if char == ',' and depth == 0:
            parts.append(current.strip())
            current = ''
        else:
            current += char
    parts.append(current.strip())
    return [part for part in parts if part]


def _selectors(css):
    """Top-level selector lists of a stylesheet (comments stripped, no at-rules)."""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    for match in re.finditer(r'([^{}]+)\{[^{}]*\}', css):
        selector = ' '.join(match.group(1).split())
        if selector and not selector.startswith('@'):
            yield selector


class DarkStylesheetTests(TestCase):
    def test_every_rule_in_the_night_stylesheet_is_scoped_to_dark_mode(self):
        # Only the switch that hides the dark logo by day may live outside the scope.
        allowed = {'.site-logo--dark'}
        leaks = []
        for selector_list in _selectors((CSS_DIR / 'fm-dark.css').read_text(encoding='utf-8')):
            for selector in _split_top_level(selector_list):
                if selector not in allowed and not selector.startswith('[data-theme="dark"]'):
                    leaks.append(selector)
        self.assertEqual(leaks, [], 'fm-dark.css must not change the day theme')

    def test_night_stylesheet_is_loaded_last_on_every_storefront_page(self):
        html = self.client.get('/').content.decode()
        self.assertRegex(html, r'css/fm-dark\.css\?v=[0-9a-f]{10}')
        self.assertLess(html.index('css/fm-ui-audit.css'), html.index('css/fm-dark.css'))
        self.assertLess(html.index('css/fm-dark.css'), html.index('</head>'))

    def test_button_backgrounds_use_the_action_token_not_the_text_token(self):
        # primary-700 is a *text* colour: light at night, so white button text vanished.
        theme = re.sub(r'/\*.*?\*/', '', (CSS_DIR / 'theme.css').read_text(encoding='utf-8'), flags=re.S)
        view_more = re.findall(r'\.view_more\s*\{[^}]*\}', theme)
        self.assertTrue(view_more)
        for rule in view_more:
            self.assertRegex(rule, r'background-color:\s*var\(--fm-action-bg')
        # …and the reverse: the background token used as a text/icon colour (mobile header icons).
        features = (CSS_DIR / 'fm-features.css').read_text(encoding='utf-8')
        self.assertIsNone(re.search(r'(?<![-\w])color:\s*var\(--fm-action-bg', features))


class DarkLogoTests(TestCase):
    def setUp(self):
        media = tempfile.mkdtemp()
        override = override_settings(MEDIA_ROOT=media)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(shutil.rmtree, media, True)
        self.site = SiteSettings.objects.order_by('pk').first() or SiteSettings.objects.create(copy_right='©')

    def _upload(self, **files):
        for field, name in files.items():
            setattr(self.site, field, SimpleUploadedFile(name, PNG, content_type='image/png'))
        self.site.save()

    def test_without_a_night_logo_the_main_logo_gets_the_light_backing(self):
        self._upload(logo='logo.png')
        html = self.client.get('/').content.decode()
        self.assertIn('site-logo site-logo--desktop"', html)
        self.assertNotIn('site-logo--dark', html)

    def test_night_logo_is_rendered_next_to_the_day_logo(self):
        self._upload(logo='logo.png', logo_dark='logo-night.png')
        html = self.client.get('/').content.decode()
        self.assertIn('site-logo--has-dark', html)
        self.assertRegex(html, r'<img src="[^"]+logo-night[^"]*\?v=[0-9a-f]+"[^>]*site-logo--dark" loading="lazy">')

    def test_night_logo_alone_is_ignored(self):
        self._upload(logo_dark='logo-night.png')
        self.assertNotIn('site-logo--dark', self.client.get('/').content.decode())


class StandalonePagesFollowTheThemeTests(TestCase):
    def test_offline_page_reads_the_saved_theme_and_has_night_colours(self):
        html = self.client.get('/offline/').content.decode()
        self.assertIn("localStorage.getItem('fm-theme') === 'dark'", html)
        self.assertIn('[data-theme="dark"] body', html)

    def test_emergency_500_page_follows_the_theme(self):
        from core.views import _FALLBACK_500

        self.assertIn("localStorage.getItem('fm-theme')==='dark'", _FALLBACK_500)
        self.assertIn('[data-theme=dark] body', _FALLBACK_500)
