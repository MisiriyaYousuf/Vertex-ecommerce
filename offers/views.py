from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .forms import CategoryOfferForm, ProductOfferForm, ReferralOfferForm
from .models import CategoryOffer, ProductOffer, ReferralOffer, ReferralProfile, ReferralReward
from .services import get_referral_profile


def _is_admin(user):
    return user.is_authenticated and user.is_superuser


def _offer_configuration_context(**extra):
    context = {
        "product_offer_form": ProductOfferForm(),
        "category_offer_form": CategoryOfferForm(),
        "referral_offer_form": ReferralOfferForm(),
        "product_offers": ProductOffer.objects.select_related("product", "product__category"),
        "category_offers": CategoryOffer.objects.select_related("category"),
        "referral_offers": ReferralOffer.objects.all(),
    }
    context.update(extra)
    return context


@login_required
@user_passes_test(_is_admin)
@never_cache
def offer_management(request):
    form_map = {
        "product": (ProductOfferForm, "product_offer_form"),
        "category": (CategoryOfferForm, "category_offer_form"),
        "referral": (ReferralOfferForm, "referral_offer_form"),
    }
    if request.method == "POST":
        offer_type = request.POST.get("offer_type")
        form_class, context_key = form_map.get(offer_type, (None, None))
        if form_class is None:
            raise Http404("Unknown offer type")
        form = form_class(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Offer created successfully.")
            return redirect("customadmin:offer_management")
        messages.error(request, "Please correct the errors below.")
        return render(request, "offer_management.html", _offer_configuration_context(**{context_key: form}))
    return render(request, "offer_management.html", _offer_configuration_context())


def _offer_class_and_form(offer_type):
    mapping = {
        "product": (ProductOffer, ProductOfferForm, "Product"),
        "category": (CategoryOffer, CategoryOfferForm, "Category"),
        "referral": (ReferralOffer, ReferralOfferForm, "Referral"),
    }
    try:
        return mapping[offer_type]
    except KeyError as exc:
        raise Http404("Unknown offer type") from exc


@login_required
@user_passes_test(_is_admin)
@never_cache
def edit_offer(request, offer_type, offer_id):
    model_class, form_class, label = _offer_class_and_form(offer_type)
    offer = get_object_or_404(model_class, id=offer_id)
    if request.method == "POST":
        form = form_class(request.POST, instance=offer)
        if form.is_valid():
            form.save()
            messages.success(request, "Offer updated successfully.")
            return redirect("customadmin:offer_management")
    else:
        form = form_class(instance=offer)
    return render(request, "offer_form.html", {"form": form, "offer": offer, "offer_label": label})


@login_required
@user_passes_test(_is_admin)
@require_POST
def toggle_offer(request, offer_type, offer_id):
    model_class, _, _ = _offer_class_and_form(offer_type)
    offer = get_object_or_404(model_class, id=offer_id)
    offer.is_active = not offer.is_active
    offer.save(update_fields=["is_active", "updated_at"])
    messages.success(request, "Offer status updated.")
    return redirect("customadmin:offer_management")


@login_required
@user_passes_test(_is_admin)
@require_POST
def delete_offer(request, offer_type, offer_id):
    model_class, _, _ = _offer_class_and_form(offer_type)
    get_object_or_404(model_class, id=offer_id).delete()
    messages.success(request, "Offer deleted.")
    return redirect("customadmin:offer_management")


@login_required
@never_cache
def referral_dashboard(request):
    profile = get_referral_profile(request.user)
    invite_url = request.build_absolute_uri(reverse("offers:referral_signup", kwargs={"token": profile.token}))
    rewards = ReferralReward.objects.filter(referrer=request.user).select_related("referred_user", "coupon")
    return render(request, "referral_dashboard.html", {
        "referral_profile": profile,
        "invite_url": invite_url,
        "rewards": rewards,
    })


@never_cache
def referral_signup(request, token):
    profile = get_object_or_404(ReferralProfile, token=token)
    request.session["signup_referral_code"] = profile.code
    messages.success(request, "Referral code applied. Complete registration to join.")
    return redirect("users:signup")
