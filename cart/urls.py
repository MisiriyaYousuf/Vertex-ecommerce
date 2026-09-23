from django.urls import path
from . import views

app_name = "cart"

urlpatterns = [
path("cart_view/", views.cart_view, name="cart"),
path("add/", views.add_to_cart, name="add_to_cart"),
path("increment/", views.increment_cart, name="increment_cart"),
path("decrement/", views.decrement_cart, name="decrement_cart"),
path("remove/", views.remove_from_cart, name="remove_from_cart"),
path("wishlist/",views.wishlist_view,name="wishlist_view"),
path("add-to-wishlist/",views.add_to_wishlist,name="add_to_wishlist"),
path("remove-from-wishlist/",views.remove_from_wishlist,name="remove_from_wishlist"),
]