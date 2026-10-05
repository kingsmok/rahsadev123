from django.urls import path
from . import views

app_name = 'downloads'
urlpatterns = [
    path('<str:token>/', views.download_file, name='download'),
]
