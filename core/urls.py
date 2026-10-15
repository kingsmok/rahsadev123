from django.urls import path
from . import views


app_name = 'core'
urlpatterns = [
    path('offline/', views.offline, name='offline'),
    path('service-worker.js', views.service_worker, name='service_worker'),
    # manifest و آیکن‌ها از «تنظیمات سایت» ساخته می‌شوند تا با تغییر نام/لوگو عوض شوند.
    path('manifest.webmanifest', views.web_manifest, name='web_manifest'),
    path('brand/icon-<int:size>.png', views.brand_icon, name='brand_icon'),
    path('', views.home, name='home'),
    path('contact/', views.contact, name='contact'),
    path('about/', views.about, name='about'),
    path('newsletter/subscribe/', views.newsletter_subscribe, name='newsletter_subscribe'),
]
