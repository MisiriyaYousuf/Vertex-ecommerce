from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
import secrets

from django.db import transaction
from django.utils import timezone

from orders.models import Coupon

from .models import CategoryOffer, ProductOffer, ReferralOffer, ReferralProfile, ReferralReward


MONEY = Decimal("0.01")
DEFAULT_REFERRAL_DISCOUNT = Decimal("10.00")
DEFAULT_REFERRAL_VALID_DAYS = 30


@dataclass(frozen=True)
class PriceBreakdown:
    original_price: Decimal
    unit_price: Decimal
    discount_amount: Decimal
    discount_percentage: Decimal
    offer_name: str
    offer_type: str

    @property
    def has_discount(self):
        return self.discount_amount > 0


def _valid_offer(queryset, today):
    return queryset.filter(is_active=True, start_date__lte=today, end_date__gte=today).first()


def get_effective_price(product, variant=None, on_date=None):
    """Return one price after selecting the largest applicable discount.

    Product and category offers are alternatives. Their percentages are compared,
    then only the better one is used. Existing product/variant sale prices are
    considered as an existing discount too, so an offer never makes an item cost
    more than it did before offers were introduced.
    """
    today = on_date or timezone.localdate()
    source = variant or product
    original_price = Decimal(source.sale_price).quantize(MONEY)
    candidates = []

    stored_discount_price = getattr(source, "discount_price", None)
    if stored_discount_price is not None and stored_discount_price < original_price:
        stored_price = Decimal(stored_discount_price).quantize(MONEY)
        stored_percentage = ((original_price - stored_price) / original_price * 100)
        candidates.append((stored_percentage, stored_price, "Special price", "stored"))

    product_offer = _valid_offer(ProductOffer.objects.filter(product=product), today)
    if product_offer:
        candidates.append((
            Decimal(product_offer.discount_percentage),
            (original_price * (Decimal("100") - Decimal(product_offer.discount_percentage)) / Decimal("100")).quantize(MONEY, rounding=ROUND_HALF_UP),
            product_offer.name,
            "product",
        ))

    category_offer = _valid_offer(CategoryOffer.objects.filter(category=product.category), today)
    if category_offer:
        candidates.append((
            Decimal(category_offer.discount_percentage),
            (original_price * (Decimal("100") - Decimal(category_offer.discount_percentage)) / Decimal("100")).quantize(MONEY, rounding=ROUND_HALF_UP),
            category_offer.name,
            "category",
        ))

    if not candidates:
        return PriceBreakdown(original_price, original_price, Decimal("0.00"), Decimal("0.00"), "", "")

    percentage, unit_price, offer_name, offer_type = max(candidates, key=lambda candidate: candidate[0])
    discount_amount = (original_price - unit_price).quantize(MONEY)
    return PriceBreakdown(
        original_price=original_price,
        unit_price=unit_price,
        discount_amount=discount_amount,
        discount_percentage=percentage.quantize(Decimal("0.01")),
        offer_name=offer_name,
        offer_type=offer_type,
    )


def add_pricing(product, variant=None):
    pricing = get_effective_price(product, variant)
    if variant is None:
        product.pricing = pricing
    else:
        variant.pricing = pricing
    return pricing


def get_referral_profile(user):
    profile, _ = ReferralProfile.objects.get_or_create(user=user, defaults={"code": generate_unique_referral_code()})
    return profile


def generate_unique_referral_code():
    for _ in range(20):
        code = secrets.token_hex(4).upper()
        if not ReferralProfile.objects.filter(code=code).exists():
            return code
    raise RuntimeError("Could not generate a unique referral code.")


def _generate_coupon_code(referrer_id):
    for _ in range(20):
        code = f"REF{referrer_id}-{secrets.token_hex(4).upper()}"
        if not Coupon.objects.filter(code=code).exists():
            return code
    raise RuntimeError("Could not generate a unique referral coupon code.")


def _current_referral_offer(today):
    return ReferralOffer.objects.filter(
        is_active=True,
        start_date__lte=today,
        end_date__gte=today,
    ).first()


@transaction.atomic
def award_referral_coupon(referred_user, referral_code):
    """Create one reward coupon for the referrer, if the code is valid."""
    referral_code = (referral_code or "").strip().upper()
    if not referral_code:
        return None

    referrer_profile = ReferralProfile.objects.select_related("user").filter(code__iexact=referral_code).first()
    if not referrer_profile or referrer_profile.user_id == referred_user.id:
        return None

    existing_reward = ReferralReward.objects.filter(referred_user=referred_user).first()
    if existing_reward:
        return existing_reward

    today = timezone.localdate()
    referral_offer = _current_referral_offer(today)
    if referral_offer:
        discount_type = referral_offer.discount_type
        discount_value = referral_offer.discount_value
        minimum_purchase = referral_offer.minimum_purchase
        maximum_discount = referral_offer.maximum_discount
        valid_days = referral_offer.valid_days
        program_name = referral_offer.name
    else:
        discount_type = ReferralOffer.PERCENTAGE
        discount_value = DEFAULT_REFERRAL_DISCOUNT
        minimum_purchase = Decimal("0.00")
        maximum_discount = None
        valid_days = DEFAULT_REFERRAL_VALID_DAYS
        program_name = "Referral reward"

    coupon = Coupon.objects.create(
        code=_generate_coupon_code(referrer_profile.user_id),
        discount_type=discount_type,
        discount_value=discount_value,
        minimum_purchase=minimum_purchase,
        maximum_discount=maximum_discount,
        start_date=today,
        end_date=today + timedelta(days=valid_days),
        usage_limit=1,
        is_active=True,
    )
    return ReferralReward.objects.create(
        referrer=referrer_profile.user,
        referred_user=referred_user,
        referral_code=referrer_profile.code,
        coupon=coupon,
        program_name=program_name,
    )
