import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def default_offer_end_date():
    return timezone.localdate() + timedelta(days=30)


def generate_referral_code():
    """Return a short, case-insensitive code suitable for sharing."""
    return secrets.token_hex(4).upper()


class TimedPercentageOffer(models.Model):
    name = models.CharField(max_length=100)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(default=default_offer_end_date)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if self.discount_percentage <= 0 or self.discount_percentage > 100:
            raise ValidationError({
                "discount_percentage": "Enter a percentage greater than 0 and no more than 100."
            })
        if self.end_date < self.start_date:
            raise ValidationError({"end_date": "The end date must be on or after the start date."})

    def __str__(self):
        return f"{self.name} ({self.discount_percentage}% off)"


class ProductOffer(TimedPercentageOffer):
    product = models.OneToOneField(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="product_offer",
    )

    class Meta:
        ordering = ["-is_active", "-created_at"]


class CategoryOffer(TimedPercentageOffer):
    category = models.OneToOneField(
        "customadmin.Category",
        on_delete=models.CASCADE,
        related_name="category_offer",
    )

    class Meta:
        ordering = ["-is_active", "-created_at"]


class ReferralOffer(models.Model):
    PERCENTAGE = "PERCENTAGE"
    FIXED = "FIXED"
    DISCOUNT_TYPE_CHOICES = [
        (PERCENTAGE, "Percentage"),
        (FIXED, "Fixed amount"),
    ]

    name = models.CharField(max_length=100)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES, default=PERCENTAGE)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=10)
    minimum_purchase = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    maximum_discount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    valid_days = models.PositiveIntegerField(default=30)
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(default=default_offer_end_date)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_active", "-created_at"]

    def clean(self):
        super().clean()
        if self.discount_value <= 0:
            raise ValidationError({"discount_value": "The reward must be greater than zero."})
        if self.discount_type == self.PERCENTAGE and self.discount_value > 100:
            raise ValidationError({"discount_value": "A percentage reward cannot exceed 100."})
        if self.end_date < self.start_date:
            raise ValidationError({"end_date": "The end date must be on or after the start date."})

    def __str__(self):
        return self.name


class ReferralProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referral_profile")
    code = models.CharField(max_length=16, unique=True, db_index=True, default=generate_referral_code)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.code}"


class ReferralReward(models.Model):
    referrer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="referral_rewards")
    referred_user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="referral_reward")
    referral_code = models.CharField(max_length=16)
    coupon = models.OneToOneField("orders.Coupon", on_delete=models.PROTECT, related_name="referral_reward")
    program_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.referrer} invited {self.referred_user}"
