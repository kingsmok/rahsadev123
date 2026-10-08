from django.urls import path
from . import views


app_name = 'core'
urlpatterns = [
    path('offline/', views.offline, name='offline'),
    path('service-worker.js', views.service_worker, name='service_worker'),
    path('', views.home, name='home'),
    path('contact/', views.contact, name='contact'),
    path('about/', views.about, name='about'),
    path('newsletter/subscribe/', views.newsletter_subscribe, name='newsletter_subscribe'),
]
