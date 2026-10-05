"""
تست‌های سازگاری با پایتون ۳.۱۴.

روی پایتون ۳.۱۴ متد ``BaseContext.__copy__`` جنگو ۵.۱ خطای
``'super' object has no attribute 'dicts'`` می‌دهد و تمام صفحاتی که از
inclusion tag استفاده می‌کنند (از جمله همهٔ صفحات /admin/) کرش می‌کنند.

این تست‌ها پیاده‌سازی اصلاح‌شده را (که در MasaiShop/compat.py قرار دارد)
روی هر نسخه‌ای از پایتون بررسی می‌کنند تا مطمئن شویم جایگزینی درست کار می‌کند.
"""

from copy import copy

from django.contrib.auth.models import User
from django.template import Context, RequestContext
from django.template.context import BaseContext
from django.test import RequestFactory, TestCase

from MasaiShop.compat import _patched_base_context_copy


class PatchedContextCopyTests(TestCase):
    """رفتار copy() با پیاده‌سازی اصلاح‌شده باید دقیقاً مثل قبل باشد."""

    def setUp(self):
        self._original = BaseContext.__copy__
        BaseContext.__copy__ = _patched_base_context_copy
        self.addCleanup(self._restore)

    def _restore(self):
        BaseContext.__copy__ = self._original

    def test_context_copy_is_independent(self):
        context = Context({"name": "رها"})
        duplicate = copy(context)

        self.assertIsInstance(duplicate, Context)
        self.assertEqual(duplicate["name"], "رها")
        self.assertIsNot(duplicate.dicts, context.dicts)

        duplicate.push({"name": "دیگری"})
        self.assertEqual(context["name"], "رها")
        self.assertEqual(duplicate["name"], "دیگری")

    def test_request_context_keeps_attributes(self):
        request = RequestFactory().get("/")
        context = RequestContext(request, {"x": 1})
        duplicate = copy(context)

        self.assertIsInstance(duplicate, RequestContext)
        self.assertIs(duplicate.request, request)
        self.assertIsNot(duplicate.render_context, context.render_context)
        self.assertEqual(duplicate["x"], 1)


class AdminRendersWithPatchedCopyTests(TestCase):
    """صفحات ادمین با پیاده‌سازی اصلاح‌شده باید بدون خطا رندر شوند."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_superuser(
            username="admin-test", email="admin@example.com", password="pass12345!"
        )

    def setUp(self):
        self._original = BaseContext.__copy__
        BaseContext.__copy__ = _patched_base_context_copy
        self.addCleanup(self._restore)
        self.client.force_login(self.admin_user)

    def _restore(self):
        BaseContext.__copy__ = self._original

    def test_admin_changelist_pages(self):
        for url in (
            "/admin/",
            "/admin/core/banner/",
            "/admin/core/contactus/",
            "/admin/product/product/",
            "/admin/blog/article/",
            "/admin/auth/user/",
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_admin_add_form(self):
        response = self.client.get("/admin/core/banner/add/")
        self.assertEqual(response.status_code, 200)
