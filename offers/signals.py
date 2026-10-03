from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ReferralProfile, generate_referral_code


@receiver(post_save, sender=get_user_model())
def create_referral_profile(sender, instance, created, **kwargs):
    if not created:
        return

    # The unique constraint protects against the extremely unlikely random-code collision.
    for _ in range(10):
        try:
            ReferralProfile.objects.create(user=instance, code=generate_referral_code())
            return
        except IntegrityError:
            continue

    raise RuntimeError("Could not generate a unique referral code.")
