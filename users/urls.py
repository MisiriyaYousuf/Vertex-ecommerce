from django.urls import path
from . import views

app_name = "users"

urlpatterns = [

    path("", views.signin, name="signin"),

    path("signup/", views.signup, name="signup"),

    path("verify-otp/", views.verify_view, name="verify_otp"),

    path("resend-otp/", views.resend_otp, name="resend_otp"),

    path('forgot-password/',views.forgot_password,name ='forgot_password'),

    path("reset-password/",views.reset_password,name="reset_password"),

    path("home/", views.home, name="home"),

    path("logout/", views.logout_view, name="logout"),

    path("profile/",views.user_profile,name="user_profile"),

    path("profile/edit/",views.edit_profile,name="edit_profile"),

    path("profile/verify-email/",views.verify_profile_email,name="verify_profile_email"),

    path('profile/resend-otp/',views.profile_resend_otp,name='profile_resend_otp'),

    path("change_password",views.change_password,name="change_password"),

    path("address/",views.address_management,name="address"),

    path("add-address/",views.add_address,name="add_address"),

    path("select-edit-address/",views.select_edit_address,name="select_edit_address"),

    path("edit-address/",views.edit_address,name="edit_address"),

    path("delete-address/",views.delete_address,name="delete_address"),


]
