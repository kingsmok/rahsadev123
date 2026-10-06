from django.contrib.auth.models import User
from django.test import TestCase

from .models import Article, Category


class ArticleVisibilityTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user('article-author', password='Safe-pass-123!')
        self.category = Category.objects.create(title='دسته آزمایشی', slug='test-category')

    def test_draft_article_is_not_publicly_accessible(self):
        article = Article.objects.create(
            author=self.author,
            title='مقاله پیش‌نویس',
            slug='draft-article',
            description='محتوای غیرعمومی',
            status='draft',
        )
        article.category.add(self.category)

        self.assertEqual(self.client.get('/blog/draft-article/').status_code, 404)
