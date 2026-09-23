from django.urls import path
from . import views

app_name = "products"

urlpatterns = [
    path(
        "products/",
        views.products,
        name="products"
    ),

    path(
        "products_details/<str:name>/",
        views.products_details,
        name="products_details"
    ),
]