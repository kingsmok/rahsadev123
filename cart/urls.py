from django.urls import path
from . import views, views_guest


app_name = 'cart'
urlpatterns = [
    path('', views.cart, name='cart'),
    path('drawer/', views.cart_drawer, name='cart_drawer'),
    path('add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('remove/<int:item_id>/', views.remove_cart_item, name='remove_cart_item'),
    path('apply_coupon/', views.apply_coupon, name='apply_coupon'),
    path('remove_coupon/', views.remove_coupon, name='remove_coupon'),
    path('shopping_payment/', views.shopping_payment, name='shopping_payment'),
    path('successful_payment/', views.successful_payment, name='successful_payment'),
    # خرید مهمان: صفحهٔ سفارش با لینک محرمانه، پیگیری سفارش و ساخت حساب اختیاری
    path('order/<str:access_token>/', views_guest.guest_order, name='guest_order'),
    path('guest-account/<str:order_number>/', views_guest.guest_account, name='guest_account'),
    path('track/', views_guest.track_order, name='track_order'),
]
