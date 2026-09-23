from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.views.decorators.cache import never_cache
from django.contrib.auth.hashers import make_password, check_password
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import secrets
import uuid
from django.contrib.auth import update_session_auth_hash
from. forms import EditProfileForm
from . import forms
from .forms import AddressForm
from . import models
from .models import UserProfile,Address,OTP
from products.models import Product
from django.db.models import F,Q, Sum


def custom_404(request):
    if request.user.is_authenticated:
        return redirect("users:home")

    return redirect("users:login")

def generate_otp(email):

    models.OTP.objects.filter(
        email=email,
        is_used=False,
        is_verified=False
    ).update(is_used=True)

    otp_code = "".join(str(secrets.randbelow(10)) for _ in range(6))

    otp = models.OTP.objects.create(
        email=email,
        otp_hash=make_password(otp_code),
        expires_at=timezone.now() + timedelta(minutes=1),
    )

    return otp, otp_code


@never_cache
def signin(request):

    if request.user.is_authenticated:

        if request.user.is_superuser:
            return redirect("customadmin:dashboard")

        return redirect("users:home")

    if request.method == "POST":

        email = request.POST.get("email")
        password = request.POST.get("password")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "Invalid email or password.")
            return redirect("users:signin")

        
        if user.is_superuser:

            user = authenticate(
                request,
                username=user.username,
                password=password
            )

            if user is not None:
                login(request, user)
                return redirect("customadmin:dashboard")

            messages.error(request, "Invalid email or password.")
            return redirect("users:signin")

        
        try:
            profile = user.profile
        except UserProfile.DoesNotExist:
            messages.error(request, "User profile not found.")
            return redirect("users:signin")

        if profile.blocked or not user.is_active:
            messages.error(
                request,
                "Your account has been blocked. Please contact the administrator."
            )
            return redirect("users:signin")

        user = authenticate(
            request,
            username=user.username,
            password=password
        )

        if user is not None:

            login(request, user)

            messages.success(
                request,
                f"Welcome {user.first_name}!"
            )

            return redirect("users:home")

        messages.error(request, "Invalid email or password.")
        return redirect("users:signin")

    return render(request, "signin.html")

@never_cache
def signup(request):
    if request.user.is_authenticated:
        return redirect("users:home")

    if request.method == "POST":
        form = forms.SignupForm(request.POST)

        if form.is_valid():

            # Store signup data in session
            request.session["signup_data"] = {
                "first_name": form.cleaned_data["first_name"],
                "last_name": form.cleaned_data["last_name"],
                "email": form.cleaned_data["email"],
                "password": form.cleaned_data["password1"],
                "phone": form.cleaned_data["phone"],
            }

            otp, otp_code = generate_otp(form.cleaned_data["email"])

            # Send OTP email
            send_mail(
                subject="Your OTP Verification Code",
                message=f"""
                        Hi {form.cleaned_data['first_name']},

                        Your signup OTP is: {otp_code}

                        It is valid for 1 minute.

                        --- HAPPY SHOPPING ---

                        Best Regards,
                        Team Vertex
                """,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[form.cleaned_data["email"]],
                fail_silently=False,
            )

            messages.success(request, "OTP sent to your email.")
            return redirect("users:verify_otp")

    else:
        form = forms.SignupForm()

    return render(request, "signup.html", {"form": form})

@never_cache
def verify_view(request):

    signup_data = request.session.get("signup_data")
    reset_data = request.session.get("password_reset_data")
    if signup_data:
        verification_type = "signup"
        email = signup_data["email"]

    elif reset_data:
        verification_type = "password_reset"
        email = reset_data["email"]

    else:
        messages.error(request, "Session expired. Please try again.")
        return redirect("users:signin")

    
    otp = models.OTP.objects.filter(
        email=email,
        is_used=False,
        is_verified=False
    ).order_by("-created_at").first()

    if request.method == "POST":

        form = forms.OTPVerificationForm(request.POST)

        if form.is_valid():

            if otp is None:
                messages.error(
                    request,
                    "No active OTP found. Please request a new OTP."
                )
                return redirect("users:forgot_password"
                                if verification_type == "password_reset"
                                else "users:signup")

            entered = form.cleaned_data["otp"]

            
            if otp.is_used:

                messages.error(
                    request,
                    "OTP has already been used."
                )

            
            elif otp.is_verified:

                messages.error(
                    request,
                    "OTP has already been verified."
                )

            elif timezone.now() > otp.expires_at:

                otp.is_used = True
                otp.save(update_fields=["is_used"])

                messages.error(
                    request,
                    "OTP expired. Please request a new OTP."
                )

            
            elif otp.attempts >= otp.max_attempts:

                otp.is_used = True
                otp.save(update_fields=["is_used"])

                messages.error(
                    request,
                    "Maximum verification attempts exceeded. Please request a new OTP."
                )

            else:

                otp.attempts += 1

                if check_password(entered, otp.otp_hash):

                    otp.is_verified = True
                    otp.is_used = True

                    otp.save(
                        update_fields=[
                            "attempts",
                            "is_verified",
                            "is_used"
                        ]
                    )

                    if verification_type == "signup":

                        username = (
                            f"{signup_data['first_name'].lower()}_"
                            f"{uuid.uuid4().hex[:8]}"
                        )

                        user = User.objects.create_user(
                            username=username,
                            first_name=signup_data["first_name"],
                            last_name=signup_data["last_name"],
                            email=signup_data["email"],
                            password=signup_data["password"],
                            is_active=True,
                        )

                        models.UserProfile.objects.create(
                            user=user,
                            phone=signup_data["phone"]
                        )

                        request.session.pop("signup_data", None)

                        messages.success(
                            request,
                            "Account created successfully."
                        )

                        return redirect("users:signin")
                    
                    elif verification_type == "password_reset":

                        request.session["password_reset_verified"] = True

                        messages.success(
                            request,
                            "Email verified successfully. You can now reset your password."
                        )

                        return redirect("users:reset_password")

                else:

                    otp.save(update_fields=["attempts"])

                    remaining = otp.max_attempts - otp.attempts

                    if remaining <= 0:

                        otp.is_used = True
                        otp.save(update_fields=["is_used"])

                        messages.error(
                            request,
                            "Maximum verification attempts exceeded. Please request a new OTP."
                        )

                    else:

                        messages.error(
                            request,
                            f"Invalid OTP. {remaining} attempt(s) remaining."
                        )

    else:
        form = forms.OTPVerificationForm()

    return render(
        request,
        "verify_otp.html",
        {
            "form": form,
            "email": email,
            "expires_at": otp.expires_at if otp else None,
            "verification_type": verification_type,
        }
    )

@never_cache
def resend_otp(request):

    signup_data = request.session.get("signup_data")
    reset_data = request.session.get("password_reset_data")


    if signup_data:

        verification_type = "signup"

        email = signup_data["email"]
        first_name = signup_data["first_name"]

        otp, otp_code = generate_otp(email)

        send_mail(
            subject="Your OTP Verification Code",

            message=f"""
                    Hi {first_name},

                    Your new signup OTP is: {otp_code}

                    This OTP is valid for 1 minute.

                    --- HAPPY SHOPPING ---

                    Best Regards,
                    Team Vertex
                                """,

            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )


    elif reset_data:

        verification_type = "password_reset"

        email = reset_data["email"]

        user = User.objects.filter(
            id=reset_data["user_id"]
        ).first()

        if not user:

            messages.error(
                request,
                "User account not found."
            )

            request.session.pop(
                "password_reset_data",
                None
            )

            return redirect(
                "users:forgot_password"
            )

        otp, otp_code = generate_otp(email)

        send_mail(
            subject="Password Reset OTP",

            message=f"""
                        Hi {user.first_name},

                        Your new password reset OTP is: {otp_code}

                        This OTP is valid for 1 minute.

                        If you did not request a password reset, please ignore this email.

                        --- HAPPY SHOPPING ---

                        Best Regards,
                        Team Vertex
                                    """,

            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )


    else:

        messages.error(
            request,
            "Session expired. Please try again."
        )

        return redirect(
            "users:signin"
        )


    messages.success(
        request,
        "A new OTP has been sent to your email."
    )

    return redirect(
        "users:verify_otp"
    )

@never_cache
def forgot_password(request):

    if request.user.is_authenticated:
        return redirect("users:home")

    if request.method == "POST":

        email = request.POST.get("email", "").strip().lower()

        if not email:
            messages.error(
                request,
                "Please enter your email address."
            )
            return redirect("users:forgot_password")

        user = User.objects.filter(
            email__iexact=email
        ).first()

        if not user:
            messages.error(
                request,
                "No account found with this email address."
            )
            return redirect("users:forgot_password")

        
        request.session.pop("password_reset_verified", None)

        
        request.session["password_reset_data"] = {
            "email": email,
            "user_id": user.id,
        }

        
        otp,otp_code = generate_otp(email)

        
        send_mail(
            subject="Password Reset OTP",
            message=f"""
                        Hi {user.first_name},

                        Your password reset OTP is: {otp_code}

                        This OTP is valid for 1 minute.

                        If you did not request a password reset, please ignore this email.

                        --- HAPPY SHOPPING ---

                        Best Regards,
                        Team Vertex
                    """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        messages.success(
            request,
            "OTP has been sent to your email."
        )

        
        return redirect("users:verify_otp")

    return render(
        request,
        "forgot_password.html"
    )

@never_cache
def reset_password(request):

    reset_data = request.session.get("password_reset_data")
    reset_verified = request.session.get("password_reset_verified")

    if not reset_data or not reset_verified:

        messages.error(request,"Please verify your OTP first.")
        return redirect("users:forgot_password")

    if request.method == "POST":
        form = forms.ResetPasswordForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data["new_password"]
            user = User.objects.filter(id=reset_data["user_id"]).first()
            if not user:
                messages.error(request,"User account not found.")
                request.session.pop("password_reset_data",None)
                request.session.pop("password_reset_verified",None)
                return redirect("users:signin")
            user.set_password(new_password)
            user.save(update_fields=["password"])
            request.session.pop("password_reset_data",None)
            request.session.pop("password_reset_verified",None)
            messages.success(request,"Password reset successfully. Please sign in.")
            return redirect("users:signin")
    else:
        form = forms.ResetPasswordForm()
    return render(request,"reset_password.html",{ "form": form })

@never_cache
@login_required
def home(request):

    if request.user.is_superuser:
        return redirect("customadmin:dashboard")

    try:
        profile = request.user.profile

    except UserProfile.DoesNotExist:

        logout(request)

        return redirect("users:signin")

    if profile.blocked or not request.user.is_active:

        logout(request)

        messages.error(
            request,
            "Your account has been blocked. Please contact the administrator."
        )

        return redirect("users:signin")

    products = (
        Product.objects
        .filter(
            is_deleted=False,
            is_active=True,
            discount_price__isnull=False,
            discount_price__gt=0,
            sale_price__isnull=False,
            discount_price__lt=F("sale_price"),
            variants__is_active=True,
            variants__quantity__gt=0,
        )
        .select_related(
            "category",
            "main_image"
        )
        .prefetch_related(
            "images",
            "variants"
        )
        .annotate(
            discount_amount=F("sale_price") - F("discount_price"),
            total_stock=Sum(
            "variants__quantity",
            filter=Q(
                    variants__is_active=True
                )
            ),
        )
        .distinct()
        .order_by(
            "-discount_amount",
            "-id"
        )[:6]
    )

    return render(
        request,
        "home.html",
        {
            "products": products
        }
    )

@never_cache
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("users:signin")

@never_cache
@login_required
def user_profile(request):

    default_address = Address.objects.filter(
        user=request.user,
        is_default=True
    ).first()

    return render(
        request,
        'user_profile.html',
        {
            'default_address': default_address,
        }
    )

@never_cache
@login_required
def edit_profile(request):

    user = request.user

    if request.method == "POST":

        form = EditProfileForm(
            request.POST,
            request.FILES,
            user=user
        )

        if form.is_valid():

            new_email = form.cleaned_data["email"]
            old_email = user.email

            # Update basic user information
            user.first_name = form.cleaned_data["first_name"]
            user.last_name = form.cleaned_data["last_name"]

            user.save(
                update_fields=[
                    "first_name",
                    "last_name"
                ]
            )

            # Update profile
            profile = user.profile

            profile.phone = form.cleaned_data["phone"]

            profile_image = form.cleaned_data.get("profile_image")

            if profile_image:
                profile.profile_image = profile_image

            profile.save()

            # --------------------------------
            # EMAIL CHANGE
            # --------------------------------

            if new_email != old_email:

                request.session["profile_email_change"] = new_email

                otp_obj, otp_code = generate_otp(new_email)

                send_mail(
                    subject="Verify your new email address",

                    message=(
                        f"Your OTP for changing your email address "
                        f"is {otp_code}.\n\n"
                        f"This OTP will expire in 1 minute."
                    ),

                    from_email=settings.DEFAULT_FROM_EMAIL,

                    recipient_list=[new_email],

                    fail_silently=False,
                )

                messages.info(
                    request,
                    "An OTP has been sent to your new email address."
                )

                return redirect(
                    "users:verify_profile_email"
                )

            # Email didn't change
            messages.success(
                request,
                "Profile updated successfully."
            )

            return redirect(
                "users:user_profile"
            )

    else:
        # GET request
        form = EditProfileForm(user=user)

    # IMPORTANT:
    # This return handles GET requests and invalid POST requests
    return render(
        request,
        "edit_profile.html",
        {
            "form": form
        }
    )

@never_cache
@login_required
def verify_profile_email(request):

    pending_email = request.session.get(
        'profile_email_change'
    )

    if not pending_email:

        messages.error(
            request,
            'Email verification session expired. Please try again.'
        )

        return redirect(
            'users:edit_profile'
        )

    if request.method == 'POST':

        entered_otp = request.POST.get(
            'otp',
            ''
        ).strip()

        if not entered_otp:

            messages.error(
                request,
                'Please enter the OTP.'
            )

            return redirect(
                'users:verify_profile_email'
            )

        otp_obj = OTP.objects.filter(
            email=pending_email,
            is_used=False,
            is_verified=False
        ).order_by(
            '-created_at'
        ).first()

        if not otp_obj:

            messages.error(
                request,
                'OTP not found. Please request a new OTP.'
            )

            return redirect(
                'users:verify_profile_email'
            )

        if timezone.now() >= otp_obj.expires_at:

            otp_obj.is_used = True

            otp_obj.save(
                update_fields=['is_used']
            )

            messages.error(
                request,
                'Your OTP has expired. Please request a new OTP.'
            )

            return redirect(
                'users:verify_profile_email'
            )

        if otp_obj.attempts >= otp_obj.max_attempts:

            otp_obj.is_used = True

            otp_obj.save(
                update_fields=['is_used']
            )

            messages.error(
                request,
                'Maximum OTP attempts reached. Please request a new OTP.'
            )

            return redirect(
                'users:verify_profile_email'
            )

        otp_obj.attempts += 1

        otp_obj.save(
            update_fields=['attempts']
        )

        if check_password(
            entered_otp,
            otp_obj.otp_hash
        ):

            otp_obj.is_verified = True
            otp_obj.is_used = True

            otp_obj.save(
                update_fields=[
                    'is_verified',
                    'is_used'
                ]
            )

            request.user.email = pending_email

            request.user.save(
                update_fields=['email']
            )

            request.session.pop(
                'profile_email_change',
                None
            )

            messages.success(
                request,
                'Your email address has been updated successfully.'
            )

            return redirect(
                'users:user_profile'
            )

        if otp_obj.attempts >= otp_obj.max_attempts:

            otp_obj.is_used = True

            otp_obj.save(
                update_fields=['is_used']
            )

            messages.error(
                request,
                'Maximum OTP attempts reached. Please request a new OTP.'
            )

        else:

            remaining_attempts = (
                otp_obj.max_attempts
                - otp_obj.attempts
            )

            messages.error(
                request,
                f'Invalid OTP. {remaining_attempts} attempt(s) remaining.'
            )

        return redirect(
            'users:verify_profile_email'
        )

    otp_obj = OTP.objects.filter(
        email=pending_email,
        is_used=False,
        is_verified=False
    ).order_by(
        '-created_at'
    ).first()

    return render(
        request,
        'verify_profile_email.html',
        {
            'email': pending_email,
            'expires_at': (
                otp_obj.expires_at
                if otp_obj
                else None
            )
        }
    )

@never_cache
@login_required
def profile_resend_otp(request):

    if request.method != 'POST':
        return redirect(
            'users:verify_profile_email'
        )

    pending_email = request.session.get(
        'profile_email_change'
    )

    print(
        'RESEND - SESSION:',
        request.session.session_key
    )

    print(
        'RESEND - PENDING EMAIL:',
        pending_email
    )

    if not pending_email:

        messages.error(
            request,
            'Email verification session expired. Please try again.'
        )

        return redirect(
            'users:edit_profile'
        )

    # Generate a NEW OTP.
    otp_obj, otp_code = generate_otp(
        pending_email
    )

    print(
        'RESEND - NEW OTP CREATED:',
        otp_obj.id
    )

    print(
        'RESEND - OTP EXPIRES:',
        otp_obj.expires_at
    )

    send_mail(
        subject='Your new email verification OTP',

        message=(
            f'Your new OTP for changing your '
            f'email address is {otp_code}. '
            f'This OTP will expire in 1 minute.'
        ),

        from_email=settings.DEFAULT_FROM_EMAIL,

        recipient_list=[
            pending_email
        ],

        fail_silently=False,
    )

    # Make absolutely sure session remains available.
    request.session['profile_email_change'] = pending_email
    request.session.modified = True

    messages.success(
        request,
        'A new verification code has been sent to your email.'
    )

    return redirect(
        'users:verify_profile_email'
    )

@never_cache
@login_required
def change_password(request):

    if request.method == "POST":

        form = forms.ChangePasswordForm(
            request.POST,
            user=request.user
        )

        if form.is_valid():

            new_password = form.cleaned_data["new_password"]

            request.user.set_password(new_password)

            request.user.save(
                update_fields=["password"]
            )

            # Keep user logged in after password change
            update_session_auth_hash(
                request,
                request.user
            )

            messages.success(
                request,
                "Your password has been changed successfully."
            )

            return redirect(
                "users:change_password"
            )

    else:

        form = forms.ChangePasswordForm(
            user=request.user
        )

    return render(
        request,
        "change_password.html",
        {
            "form": form
        }
    )

@never_cache
@login_required
def address_management(request):

    addresses = Address.objects.filter(user=request.user).order_by('-is_default','-created_at')
    context = {'addresses': addresses}
    return render(request,'address.html',context)

@never_cache
@login_required
def add_address(request):

    if request.method == "GET":

        if request.GET.get("from") == "checkout":

            request.session[
                "address_return"
            ] = "checkout"

    return_to = request.session.get(
        "address_return",
        "address"
    )

    has_default_address = Address.objects.filter(
        user=request.user,
        is_default=True
    ).exists()

    if request.method == "POST":

        form = AddressForm(request.POST)

        if form.is_valid():

            address = form.save(
                commit=False
            )

            address.user = request.user

            if has_default_address:

                address.is_default = False

            elif address.is_default:

                Address.objects.filter(
                    user=request.user,
                    is_default=True
                ).update(
                    is_default=False
                )

            address.save()

            request.session.pop(
                "address_return",
                None
            )

            messages.success(
                request,
                "Address added successfully."
            )

            if return_to == "checkout":

                return redirect(
                    "orders:checkout"
                )

            return redirect(
                "users:address"
            )

    else:

        form = AddressForm()

    context = {
        "form": form,
        "has_default_address": has_default_address,
    }

    return render(
        request,
        "add_address.html",
        context
    )

@never_cache
@login_required
def select_edit_address(request):

    if request.method == "POST":

        address_id = request.POST.get(
            "address_id"
        )

        address = get_object_or_404(
            Address,
            id=address_id,
            user=request.user
        )

        request.session[
            "edit_address_id"
        ] = address.id


        return_to = request.POST.get(
            "return_to"
        )


        if return_to == "checkout":

            request.session[
                "edit_address_return"
            ] = "checkout"

        else:

            request.session[
                "edit_address_return"
            ] = "address"


        return redirect(
            "users:edit_address"
        )


    return redirect(
        "users:address"
    )

@never_cache
@login_required
def edit_address(request):

    address_id = request.session.get("edit_address_id")

    if not address_id:

        messages.error(
            request,
            "No address selected for editing."
        )

        return redirect("users:address")

    address = get_object_or_404(
        Address,
        id=address_id,
        user=request.user
    )

    another_default_exists = Address.objects.filter(
        user=request.user,
        is_default=True
    ).exclude(
        id=address.id
    ).exists()

    if request.method == "POST":

        form = AddressForm(
            request.POST,
            instance=address
        )

        if form.is_valid():

            with transaction.atomic():

                updated_address = form.save(
                    commit=False
                )

                updated_address.user = request.user

                # If another address is already default,
                # do not allow this address to become default.
                if another_default_exists:

                    updated_address.is_default = address.is_default

                elif updated_address.is_default:

                    # Make sure no other address is default.
                    Address.objects.filter(
                        user=request.user,
                        is_default=True
                    ).exclude(
                        id=address.id
                    ).update(
                        is_default=False
                    )

                updated_address.save()

            # Remove edit session data
            request.session.pop(
                "edit_address_id",
                None
            )

            # Check where the edit was initiated from
            return_to = request.session.pop(
                "edit_address_return",
                "address"
            )

            messages.success(
                request,
                "Address updated successfully."
            )

            # If edited from checkout,
            # return to checkout.
            if return_to == "checkout":

                return redirect(
                    "orders:checkout"
                )

            # Otherwise return to My Address
            return redirect(
                "users:address"
            )

    else:

        form = AddressForm(
            instance=address
        )

    context = {
        "form": form,
        "address": address,
        "another_default_exists": another_default_exists,
    }

    return render(
        request,
        "edit_address.html",
        context
    )

@never_cache
@login_required
def delete_address(request):

    if request.method != "POST":
        return redirect("users:address")

    address_id = request.POST.get("address_id")

    if not address_id:
        messages.error(
            request,
            "No address selected for deletion."
        )
        return redirect("users:address")

    address = get_object_or_404(
        Address,
        id=address_id,
        user=request.user
    )

    was_default = address.is_default

    address.delete()

    if was_default:

        next_address = Address.objects.filter(
            user=request.user
        ).order_by("-created_at").first()

        if next_address:
            next_address.is_default = True
            next_address.save(
                update_fields=["is_default"]
            )

    messages.success(
        request,
        "Address deleted successfully."
    )

    return redirect("users:address")

