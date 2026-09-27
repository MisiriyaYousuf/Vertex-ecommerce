import razorpay

from django.conf import settings


def get_razorpay_client():

    if not settings.RAZORPAY_KEY_ID:
        raise ValueError(
            "RAZORPAY_KEY_ID is not configured."
        )

    if not settings.RAZORPAY_KEY_SECRET:
        raise ValueError(
            "RAZORPAY_KEY_SECRET is not configured."
        )

    return razorpay.Client(
        auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET,
        )
    )


def create_razorpay_order(order):

    client = get_razorpay_client()

    amount_paise = int(
        order.total_amount * 100
    )

    razorpay_order = client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "receipt": f"order_{order.id}",
        "notes": {
            "django_order_id": str(order.id),
            "user_id": str(order.user_id),
        },
    })

    order.razorpay_order_id = razorpay_order["id"]

    order.save(
        update_fields=[
            "razorpay_order_id",
            "updated_at",
        ]
    )

    return razorpay_order