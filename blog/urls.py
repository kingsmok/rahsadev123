from django.urls import path, re_path
from django.views.generic import RedirectView
from . import views

app_name = 'blog'
urlpatterns = [
    path('', views.article_list, name='article_list'),
    path('category/', RedirectView.as_view(pattern_name='blog:article_list', permanent=True), name='redirect_category'),
    re_path(r'category/(?P<slug>[-\w]+)/$', views.category_article, name='article_category'),
    re_path(r'(?P<slug>[-\w]+)/$', views.article_detail, name='article_detail'),
]
