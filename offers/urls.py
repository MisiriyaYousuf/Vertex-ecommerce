from django.urls import path

from . import views

app_name = "offers"

urlpatterns = [
    path("referrals/", views.referral_dashboard, name="referral_dashboard"),
    path("ref/<uuid:token>/", views.referral_signup, name="referral_signup"),
]
