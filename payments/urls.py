from django.urls import path
from . import views

app_name = 'payments'
urlpatterns = [
    path('start/<str:order_number>/', views.start_payment, name='start'),
    path('callback/', views.callback, name='callback'),
    path('successful/<str:order_number>/', views.successful_payment_done, name='successful_done'),
]
