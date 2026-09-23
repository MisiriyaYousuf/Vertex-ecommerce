from django.urls import path
from . import views

app_name = 'customadmin' 
urlpatterns = [
    path('',views.dashboard,name='dashboard'),
    path("logout/", views.logout_view, name="logout"),
    path("users/",views.user_management,name="user_management"),
    path("users/block/",views.block_user,name="block_user"),
    path("users/unblock/",views.unblock_user,name="unblock_user"),
    path("categories/",views.category_management,name="category_management"),
    path("categories/edit/",views.edit_category,name="edit_category"),
    path("categories/delete/",views.delete_category,name="delete_category"),
    path("products/add/",views.add_product,name="add_product"),
    path("products/",views.list_product,name="list_product"),
    path('view_product/',views.view_product,name='view_product'),
    path("products/edit/",views.edit_product,name="edit_product"),
    path("products/delete/",views.delete_product,name="delete_product"),
    path("products/delete-image/",views.delete_product_image,name="delete_product_image"),
    path("products/delete-variant-image/",views.delete_variant_image,name="delete_variant_image"),
    path("orders/",views.order_management,name="order_management"),
    path("orders/detail/",views.admin_order_detail,name="admin_order_detail"),
    path("orders/update-status/",views.update_order_status,name="update_order_status"),
    path("inventory/",views.inventory_management,name="inventory_management"),
]
