from django.shortcuts import render, get_object_or_404
from .models import Article, Category
from django.core.paginator import Paginator


def _published_articles():
    """Relations rendered by article cards and headers, fetched in bulk."""
    return Article.objects.filter(status='published').select_related(
        'author', 'author__profile'
    ).prefetch_related('category')


def get_pages_to_show(current_page, total_pages):
    if total_pages <= 3:
        return list(range(1, total_pages + 1))

    if current_page <= 2:
        return [1, 2, 3, '...', total_pages]

    if current_page >= total_pages - 1:
        return [1, '...', total_pages - 2, total_pages - 1, total_pages]

    return [1, '...', current_page - 1, current_page, current_page + 1, '...', total_pages]


def article_list(request):
    categories = Category.objects.all()
    articles = _published_articles()
    latest_articles = _published_articles().order_by('-created_at')[:6]

    # Pagination
    page_number = request.GET.get('page')
    paginator = Paginator(articles, 4)
    object_list = paginator.get_page(page_number)
    pages_to_show = get_pages_to_show(object_list.number, paginator.num_pages)

    context = {
        'article_categories': categories,
        'articles': object_list,
        'latest_articles': latest_articles,
        'pages_to_show': pages_to_show,
    }
    return render(request, 'blog/article_list.html', context)


def category_article(request, slug):
    category = get_object_or_404(Category, slug=slug)
    categories = Category.objects.all()
    articles = _published_articles().filter(category=category)
    latest_articles = _published_articles().order_by('-created_at')[:6]

    # Pagination
    page_number = request.GET.get('page')
    paginator = Paginator(articles, 4)
    object_list = paginator.get_page(page_number)
    pages_to_show = get_pages_to_show(object_list.number, paginator.num_pages)

    context = {
        'category': category,
        'article_categories': categories,
        'articles': object_list,
        'latest_articles': latest_articles,
        'pages_to_show': pages_to_show,
    }
    return render(request, 'blog/category_article.html', context)


def article_detail(request, slug):
    categories = Category.objects.all()
    # A guessed slug must not expose an unpublished editorial draft.
    article = get_object_or_404(_published_articles(), slug=slug)
    latest_articles = _published_articles().exclude(id=article.id).order_by('-created_at')[:6]

    viewed_article = request.session.get('viewed_article', [])
    if article.id not in viewed_article:
        article.views += 1
        article.save(update_fields=['views'])
        viewed_article.append(article.id)
        request.session['viewed_article'] = viewed_article

    context = {
        'article_categories': categories,
        'article': article,
        'latest_articles': latest_articles,
    }
    return render(request, 'blog/article_detail.html', context)
