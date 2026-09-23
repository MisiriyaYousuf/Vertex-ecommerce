from django.contrib import admin
from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render


def custom_404(request, exception):
    return render(request, "404.html", status=404)


urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('', include('users.urls')),
    path('accounts/', include('allauth.urls')),
    path('admin/',include('customadmin.urls')),
    path('products/',include('products.urls')),
    path('cart/',include('cart.urls')),
    path("orders/",include("orders.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
   
handler404 = "project.urls.custom_404"