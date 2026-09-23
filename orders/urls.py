from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [

    path("checkout/",views.checkout,name="checkout"),
    path("order-detail/",views.order_detail,name="order_detail"),
    path("place-order/",views.place_order,name="place_order"),
    path("order-success/",views.order_success,name="order_success"),
    path("download-invoice/",views.download_invoice,name="download_invoice",),
    path("orders/",views.order_list,name="order_list"),
    path("view-order/", views.view_order, name="view_order"),
    path("cancel-order/", views.cancel_order, name="cancel_order"),
    path("cancellation-success/",views.cancellation_success,name="cancellation_success"),
    path("return-order/", views.return_order, name="return_order"),
    path("return-success/", views.return_success, name="return_success"),   

]