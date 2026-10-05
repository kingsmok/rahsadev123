from django.urls import path
from .views import detail
app_name='pages'
urlpatterns=[path('<slug:slug>/', detail, name='detail')]
