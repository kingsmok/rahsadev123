from django.urls import path, re_path
from .views import detail

app_name = 'pages'
urlpatterns = [
    # پشتیبانی از نامک‌های فارسی (یونیکد)
    re_path(r'(?P<slug>[\w-]+)/$', detail, name='detail'),
]
