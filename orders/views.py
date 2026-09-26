from decimal import Decimal
from datetime import timedelta
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from cart.models import Cart
from products.models import Product, ProductVariant
from users.models import Address

from .forms import CheckoutForm
from .models import Order, OrderItem



MAX_CART_QUANTITY = 5


# ============================================================
# ORDER STATUS CALCULATION
# ============================================================

def update_status(order):
    statuses = list(
        order.items.values_list(
            "status",
            flat=True
        )
    )

    if not statuses:
        order.status = "Pending"

    elif all(
        status == "Cancelled"
        for status in statuses
    ):
        order.status = "Cancelled"

    elif all(
        status == "Returned"
        for status in statuses
    ):
        order.status = "Returned"

    elif all(
        status in ["Cancelled", "Returned"]
        for status in statuses
    ):
        order.status = "Returned"

    elif all(
        status == "Delivered"
        for status in statuses
    ):
        order.status = "Delivered"

    elif all(
        status in [
            "Delivered",
            "Returned",
            "Cancelled",
        ]
        for status in statuses
    ):
        order.status = "Delivered"

    elif any(
        status == "Delivered"
        for status in statuses
    ):
        order.status = "Partially Delivered"

    elif all(
        status in [
            "Shipped",
            "Out for Delivery",
            "Delivered",
            "Cancelled",
            "Returned",
        ]
        for status in statuses
    ):
        order.status = "Shipped"

    elif any(
        status in [
            "Shipped",
            "Out for Delivery",
        ]
        for status in statuses
    ):
        order.status = "Partially Shipped"

    elif all(
        status == "Processing"
        for status in statuses
    ):
        order.status = "Processing"

    else:
        order.status = "Pending"

    order.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )


# ============================================================
# PURCHASE LABEL
# ============================================================

def get_purchase_label(product, variant=None):

    source = variant if variant is not None else product

    if not source:
        return ""

    parts = []

    if getattr(source, "color", None):
        parts.append(source.color)

    if getattr(source, "size", None):
        parts.append(source.size)

    if parts:
        return " / ".join(parts)

    if getattr(source, "product_code", None):
        return source.product_code

    if variant is not None:
        return f"Variant #{variant.id}"

    return ""


# ============================================================
# PRODUCT PRICING
# ============================================================

def get_product_pricing(product, quantity, variant=None):

    source = variant if variant else product

    if (
        source.discount_price is not None
        and source.discount_price < source.sale_price
    ):
        unit_price = source.discount_price

        unit_discount = (
            source.sale_price
            - source.discount_price
        )

    else:
        unit_price = source.sale_price
        unit_discount = Decimal("0.00")

    original_total = (
        source.sale_price * quantity
    )

    discount_total = (
        unit_discount * quantity
    )

    final_total = (
        unit_price * quantity
    )

    return (
        original_total,
        discount_total,
        final_total,
        unit_price,
        unit_discount,
    )


# ============================================================
# CHECKOUT
# ============================================================

@login_required
@never_cache
def checkout(request):

    cart_items = (
        Cart.objects
        .filter(user=request.user)
        .select_related(
            "product",
            "product__category",
            "product__main_image",
            "variant",
        )
        .prefetch_related(
            "product__images",
            "variant__images",
        )
    )

    if not cart_items.exists():

        messages.warning(
            request,
            "Your cart is empty."
        )

        return redirect("cart:cart")

    for item in cart_items:

        product = item.product
        variant = item.variant

        if not product:

            messages.error(
                request,
                "A product in your cart is no longer available."
            )

            return redirect("cart:cart")

        if not product.is_active:

            messages.error(
                request,
                f"{product.name} is currently unavailable."
            )

            return redirect("cart:cart")

        if product.is_deleted:

            messages.error(
                request,
                f"{product.name} is no longer available."
            )

            return redirect("cart:cart")

        if not product.category:

            messages.error(
                request,
                f"{product.name} is no longer available."
            )

            return redirect("cart:cart")

        if (
            product.category.is_trashed
            or getattr(
                product.category,
                "is_blocked",
                False
            )
        ):

            messages.error(
                request,
                f"{product.name} is no longer available."
            )

            return redirect("cart:cart")

        if variant:

            if variant.product_id != product.id:

                messages.error(
                    request,
                    f"Invalid variant selected for "
                    f"{product.name}."
                )

                return redirect("cart:cart")

            if not variant.is_active:

                messages.error(
                    request,
                    f"The selected variant for "
                    f"{product.name} is unavailable."
                )

                return redirect("cart:cart")

            available_quantity = variant.quantity

        else:

            available_quantity = product.quantity

        if available_quantity <= 0:

            if variant:

                messages.error(
                    request,
                    f"{product.name} "
                    f"({get_purchase_label(product, variant)}) "
                    f"is out of stock."
                )

            else:

                messages.error(
                    request,
                    f"{product.name} is out of stock."
                )

            return redirect("cart:cart")

        if item.quantity > MAX_CART_QUANTITY:

            messages.error(
                request,
                f"You can add a maximum of "
                f"{MAX_CART_QUANTITY} items of "
                f"{product.name}."
            )

            return redirect("cart:cart")

        if item.quantity > available_quantity:

            if variant:

                messages.error(
                    request,
                    f"Only {available_quantity} unit(s) of "
                    f"{product.name} "
                    f"({get_purchase_label(product, variant)}) "
                    f"are available."
                )

            else:

                messages.error(
                    request,
                    f"Only {available_quantity} unit(s) of "
                    f"{product.name} are available."
                )

            return redirect("cart:cart")

    addresses = (
        Address.objects
        .filter(
            user=request.user,
            is_deleted=False
        )
        .order_by(
            "-is_default",
            "-created_at",
        )
    )

    if not addresses.exists():

        messages.warning(
            request,
            "Please add a delivery address before checkout."
        )

        return redirect("users:address")

    default_address = addresses.filter(
        is_default=True
    ).first()

    if default_address is None:
        default_address = addresses.first()

    subtotal = Decimal("0.00")
    discount_amount = Decimal("0.00")

    for item in cart_items:

        (
            original_total,
            item_discount,
            item_total,
            unit_price,
            unit_discount,
        ) = get_product_pricing(
            item.product,
            item.quantity,
            item.variant,
        )

        subtotal += original_total
        discount_amount += item_discount

    tax = Decimal("0.00")
    shipping_charge = Decimal("0.00")

    total_amount = (
        subtotal
        - discount_amount
        + tax
        + shipping_charge
    )

    total_items = sum(
        item.quantity
        for item in cart_items
    )

    delivery_date = (
        timezone.localdate()
        + timedelta(days=4)
    )

    if request.method == "POST":

        form = CheckoutForm(
            request.user,
            request.POST
        )

        if form.is_valid():

            address = form.cleaned_data["address"]

            payment_method = form.cleaned_data[
                "payment_method"
            ]

            if (
                address.user_id != request.user.id
                or address.is_deleted
            ):

                messages.error(
                    request,
                    "Invalid delivery address selected."
                )

                return redirect(
                    "orders:checkout"
                )

            request.session[
                "checkout_address_id"
            ] = address.id

            request.session[
                "checkout_payment_method"
            ] = payment_method

            request.session[
                "checkout_delivery_date"
            ] = str(delivery_date)

            return redirect(
                "orders:order_detail"
            )

    else:

        form = CheckoutForm(
            request.user,
            initial={
                "address": default_address,
                "payment_method": "COD",
            }
        )

    context = {

        "form": form,

        "cart_items": cart_items,

        "addresses": addresses,

        "default_address": default_address,

        "subtotal": subtotal,

        "discount_amount": discount_amount,

        "tax": tax,

        "shipping_charge": shipping_charge,

        "total_amount": total_amount,

        "delivery_date": delivery_date,

        "total_items": total_items,

        "payment_method": "COD",

        "payment_method_display": "Cash on Delivery",
    }

    return render(
        request,
        "checkout.html",
        context,
    )


# ============================================================
# ORDER DETAIL / ORDER REVIEW
# ============================================================

@login_required
@never_cache
def order_detail(request, order_id=None):

    if order_id:

        order = (
            Order.objects
            .filter(
                id=order_id,
                user=request.user,
            )
            .prefetch_related(
                "items__product__images",
                "items__product__main_image",
                "items__variant__images",
            )
            .select_related(
                "address",
            )
            .first()
        )

        if not order:

            messages.error(
                request,
                "Order not found."
            )

            return redirect(
                "orders:order_list"
            )

        for item in order.items.all():

            if item.is_returned:

                item.display_status = "Returned"

            elif item.is_cancelled:

                item.display_status = "Cancelled"

            else:

                item.display_status = (
                    getattr(
                        item,
                        "status",
                        order.status
                    )
                )

            item.purchase_label = get_purchase_label(
                item.product,
                item.variant,
            )

            item.variant_label = item.purchase_label

            variant = item.variant
            product = item.product

            if variant:

                variant_images = list(
                    variant.images.all()
                )

            else:

                variant_images = []

            product_images = (
                list(product.images.all())
                if product
                else []
            )

            if variant_images:

                item.display_images = variant_images

            elif product_images:

                item.display_images = product_images

            elif product and product.main_image:

                item.display_images = [
                    product.main_image
                ]

            else:

                item.display_images = []

            item.main_display_image = (
                item.display_images[0]
                if item.display_images
                else None
            )

        return render(
            request,
            "order_detail.html",
            {
                "order": order,
                "is_review": False,
            },
        )

    if request.method == "POST":

        action = request.POST.get(
            "action",
            "",
        ).strip()

        if action == "place_order":

            return redirect(
                "orders:place_order"
            )

        if action in [
            "increase",
            "decrease",
            "delete",
        ]:

            cart_id = request.POST.get(
                "cart_id"
            )

            if not cart_id:

                messages.error(
                    request,
                    "Cart item not found."
                )

                return redirect(
                    "orders:order_detail"
                )

            cart_item = (
                Cart.objects
                .filter(
                    id=cart_id,
                    user=request.user,
                )
                .select_related(
                    "product",
                    "product__category",
                    "product__main_image",
                    "variant",
                )
                .first()
            )

            if not cart_item:

                messages.error(
                    request,
                    "Cart item not found."
                )

                return redirect(
                    "orders:order_detail"
                )

            if action == "delete":

                product_name = (
                    cart_item.product.name
                    if cart_item.product
                    else "Product"
                )

                cart_item.delete()

                messages.success(
                    request,
                    f"{product_name} was removed from your order."
                )

                return redirect(
                    "orders:order_detail"
                )

            product = cart_item.product
            variant = cart_item.variant

            if not product:

                messages.error(
                    request,
                    "This product is no longer available."
                )

                return redirect(
                    "orders:order_detail"
                )

            if not product.is_active:

                messages.error(
                    request,
                    f"{product.name} is currently unavailable."
                )

                return redirect(
                    "orders:order_detail"
                )

            if product.is_deleted:

                messages.error(
                    request,
                    f"{product.name} is no longer available."
                )

                return redirect(
                    "orders:order_detail"
                )

            if not product.category:

                messages.error(
                    request,
                    f"{product.name} is no longer available."
                )

                return redirect(
                    "orders:order_detail"
                )

            if (
                product.category.is_trashed
                or getattr(
                    product.category,
                    "is_blocked",
                    False,
                )
            ):

                messages.error(
                    request,
                    f"{product.name} is no longer available."
                )

                return redirect(
                    "orders:order_detail"
                )

            if variant:

                if variant.product_id != product.id:

                    messages.error(
                        request,
                        "Invalid product variant."
                    )

                    return redirect(
                        "orders:order_detail"
                    )

                if not variant.is_active:

                    messages.error(
                        request,
                        f"The selected variant for "
                        f"{product.name} is unavailable."
                    )

                    return redirect(
                        "orders:order_detail"
                    )

                available_quantity = variant.quantity

            else:

                available_quantity = product.quantity

            if action == "increase":

                max_quantity = min(
                    MAX_CART_QUANTITY,
                    available_quantity,
                )

                if max_quantity <= 0:

                    messages.error(
                        request,
                        "This item is out of stock."
                    )

                elif cart_item.quantity < max_quantity:

                    cart_item.quantity += 1

                    cart_item.save(
                        update_fields=[
                            "quantity",
                            "updated_at",
                        ]
                    )

                    messages.success(
                        request,
                        "Quantity increased."
                    )

                else:

                    if available_quantity < MAX_CART_QUANTITY:

                        messages.warning(
                            request,
                            f"Only {available_quantity} "
                            f"unit(s) are available."
                        )

                    else:

                        messages.warning(
                            request,
                            f"You can add a maximum of "
                            f"{MAX_CART_QUANTITY} items."
                        )

            elif action == "decrease":

                if cart_item.quantity > 1:

                    cart_item.quantity -= 1

                    cart_item.save(
                        update_fields=[
                            "quantity",
                            "updated_at",
                        ]
                    )

                    messages.success(
                        request,
                        "Quantity decreased."
                    )

                else:

                    cart_item.delete()

                    messages.success(
                        request,
                        "Item removed from your order."
                    )

            return redirect(
                "orders:order_detail"
            )

    # ========================================================
    # ORDER REVIEW PAGE
    # ========================================================

    cart_items = (
        Cart.objects
        .filter(
            user=request.user,
        )
        .select_related(
            "product",
            "product__category",
            "product__main_image",
            "variant",
        )
        .prefetch_related(
            "product__images",
            "variant__images",
        )
        .order_by(
            "-created_at",
            "-id",
        )
    )

    if not cart_items.exists():

        messages.warning(
            request,
            "Your cart is empty."
        )

        return redirect(
            "cart:cart"
        )

    for item in cart_items:

        product = item.product
        variant = item.variant

        if not product:

            messages.error(
                request,
                "A product in your cart is unavailable."
            )

            return redirect(
                "cart:cart"
            )

        if not product.is_active:

            messages.error(
                request,
                f"{product.name} is currently unavailable."
            )

            return redirect(
                "cart:cart"
            )

        if product.is_deleted:

            messages.error(
                request,
                f"{product.name} is no longer available."
            )

            return redirect(
                "cart:cart"
            )

        if not product.category:

            messages.error(
                request,
                f"{product.name} is no longer available."
            )

            return redirect(
                "cart:cart"
            )

        if (
            product.category.is_trashed
            or getattr(
                product.category,
                "is_blocked",
                False,
            )
        ):

            messages.error(
                request,
                f"{product.name} is no longer available."
            )

            return redirect(
                "cart:cart"
            )

        if variant:

            if variant.product_id != product.id:

                messages.error(
                    request,
                    f"Invalid variant selected for "
                    f"{product.name}."
                )

                return redirect(
                    "cart:cart"
                )

            if not variant.is_active:

                messages.error(
                    request,
                    f"The selected variant for "
                    f"{product.name} is unavailable."
                )

                return redirect(
                    "cart:cart"
                )

            available_quantity = variant.quantity

        else:

            available_quantity = product.quantity

        if available_quantity <= 0:

            if variant:

                messages.error(
                    request,
                    f"{product.name} "
                    f"({get_purchase_label(product, variant)}) "
                    f"is out of stock."
                )

            else:

                messages.error(
                    request,
                    f"{product.name} is out of stock."
                )

            return redirect(
                "cart:cart"
            )

        if item.quantity > MAX_CART_QUANTITY:

            messages.error(
                request,
                f"Maximum allowed quantity is "
                f"{MAX_CART_QUANTITY}."
            )

            return redirect(
                "cart:cart"
            )

        if item.quantity > available_quantity:

            if variant:

                messages.error(
                    request,
                    f"Only {available_quantity} unit(s) of "
                    f"{product.name} "
                    f"({get_purchase_label(product, variant)}) "
                    f"are available."
                )

            else:

                messages.error(
                    request,
                    f"Only {available_quantity} unit(s) of "
                    f"{product.name} are available."
                )

            return redirect(
                "cart:cart"
            )

    address_id = request.session.get(
        "checkout_address_id"
    )

    payment_method = request.session.get(
        "checkout_payment_method",
        "COD",
    )

    delivery_date_string = request.session.get(
        "checkout_delivery_date"
    )

    address = None

    if address_id:

        address = (
            Address.objects
            .filter(
                id=address_id,
                user=request.user,
            )
            .first()
        )

    if not address:

        address = (
            Address.objects
            .filter(
                user=request.user,
                is_default=True,
            )
            .first()
        )

    if not address:

        address = (
            Address.objects
            .filter(
                user=request.user,
            )
            .order_by(
                "-created_at"
            )
            .first()
        )

    if not address:

        messages.warning(
            request,
            "Please add a delivery address."
        )

        return redirect(
            "users:address"
        )

    if delivery_date_string:

        try:

            delivery_date = (
                timezone.datetime.strptime(
                    delivery_date_string,
                    "%Y-%m-%d",
                ).date()
            )

        except ValueError:

            delivery_date = (
                timezone.localdate()
                + timedelta(days=4)
            )

    else:

        delivery_date = (
            timezone.localdate()
            + timedelta(days=4)
        )

    review_items = []

    subtotal = Decimal("0.00")
    discount_amount = Decimal("0.00")
    total_items = 0

    for item in cart_items:

        product = item.product
        variant = item.variant

        (
            original_total,
            item_discount,
            item_total,
            unit_price,
            unit_discount,
        ) = get_product_pricing(
            product,
            item.quantity,
            variant,
        )

        if variant:

            variant_images = list(
                variant.images.all()
            )

        else:

            variant_images = []

        product_images = list(
            product.images.all()
        )

        if variant_images:

            thumbnails = variant_images

        elif product_images:

            thumbnails = product_images

        elif product.main_image:

            thumbnails = [
                product.main_image
            ]

        else:

            thumbnails = []

        main_image = (
            thumbnails[0]
            if thumbnails
            else None
        )

        original_price = (
            variant.sale_price
            if variant
            else product.sale_price
        )

        available_quantity = (
            variant.quantity
            if variant
            else product.quantity
        )

        variant_label = get_purchase_label(
            product,
            variant,
        )

        review_items.append(
            {
                "cart_id": item.id,
                "product": product,
                "product_id": product.id,
                "product_name": product.name,
                "description": product.description,
                "variant": variant,
                "variant_id": (
                    variant.id
                    if variant
                    else None
                ),
                "variant_label": variant_label,
                "quantity": item.quantity,
                "unit_price": unit_price,
                "original_price": original_price,
                "unit_discount": unit_discount,
                "discount": item_discount,
                "item_total": item_total,
                "main_image": main_image,
                "thumbnails": thumbnails,
                "max_quantity": min(
                    MAX_CART_QUANTITY,
                    available_quantity,
                ),
            }
        )

        subtotal += original_total
        discount_amount += item_discount
        total_items += item.quantity

    tax = Decimal("0.00")
    shipping_charge = Decimal("0.00")

    grand_total = (
        subtotal
        - discount_amount
        + tax
        + shipping_charge
    )

    payment_method_display = dict(
        Order.PAYMENT_METHOD_CHOICES
    ).get(
        payment_method,
        payment_method,
    )

    context = {

        "review_items": review_items,

        "address": address,

        "payment_method": payment_method,

        "payment_method_display": (
            payment_method_display
        ),

        "delivery_date": delivery_date,

        "subtotal": subtotal,

        "discount_amount": discount_amount,

        "tax": tax,

        "shipping_charge": shipping_charge,

        "grand_total": grand_total,

        "total_items": total_items,

        "is_review": True,
    }

    return render(
        request,
        "order_detail.html",
        context,
    )


# ============================================================
# PLACE ORDER
# ============================================================

@login_required
@never_cache
@transaction.atomic
def place_order(request):

    if request.method != "POST":

        return redirect(
            "orders:order_detail"
        )

    address_id = request.session.get(
        "checkout_address_id"
    )

    payment_method = request.session.get(
        "checkout_payment_method",
        "COD",
    )

    delivery_date_string = request.session.get(
        "checkout_delivery_date"
    )

    if not address_id:

        messages.error(
            request,
            "Please select a delivery address."
        )

        return redirect(
            "orders:checkout"
        )

    address = (
        Address.objects
        .filter(
            id=address_id,
            user=request.user,
        )
        .first()
    )

    if not address:

        messages.error(
            request,
            "Selected address is not available."
        )

        return redirect(
            "orders:checkout"
        )

    if delivery_date_string:

        try:

            delivery_date = (
                timezone.datetime.strptime(
                    delivery_date_string,
                    "%Y-%m-%d",
                ).date()
            )

        except ValueError:

            delivery_date = (
                timezone.localdate()
                + timedelta(days=4)
            )

    else:

        delivery_date = (
            timezone.localdate()
            + timedelta(days=4)
        )

    # ========================================================
    # LOCK CART ROWS
    # ========================================================

    cart_items = list(
        Cart.objects
        .select_for_update()
        .filter(
            user=request.user
        )
        .select_related(
            "product",
            "product__category",
            "variant",
        )
    )

    if not cart_items:

        messages.error(
            request,
            "Your cart is empty."
        )

        return redirect(
            "cart:cart"
        )

    validated_items = []

    subtotal = Decimal("0.00")
    discount_amount = Decimal("0.00")

    for cart_item in cart_items:

        product = cart_item.product
        variant = cart_item.variant

        if not product:

            messages.error(
                request,
                "A product in your cart is unavailable."
            )

            return redirect(
                "cart:cart"
            )

        if not product.is_active:

            messages.error(
                request,
                f"{product.name} is currently unavailable."
            )

            return redirect(
                "cart:cart"
            )

        if product.is_deleted:

            messages.error(
                request,
                f"{product.name} is no longer available."
            )

            return redirect(
                "cart:cart"
            )

        if not product.category:

            messages.error(
                request,
                f"{product.name} is no longer available."
            )

            return redirect(
                "cart:cart"
            )

        if (
            product.category.is_trashed
            or getattr(
                product.category,
                "is_blocked",
                False
            )
        ):

            messages.error(
                request,
                f"{product.name} is no longer available."
            )

            return redirect(
                "cart:cart"
            )

        if cart_item.variant_id:

            variant = (
                ProductVariant.objects
                .select_for_update()
                .filter(
                    id=cart_item.variant_id,
                    product_id=product.id,
                )
                .first()
            )

            if not variant:

                messages.error(
                    request,
                    f"The selected variant for "
                    f"{product.name} is no longer available."
                )

                return redirect(
                    "cart:cart"
                )

            if not variant.is_active:

                messages.error(
                    request,
                    f"The selected variant for "
                    f"{product.name} is unavailable."
                )

                return redirect(
                    "cart:cart"
                )

            available_quantity = variant.quantity

        else:

            product = (
                Product.objects
                .select_for_update()
                .select_related("category")
                .filter(
                    id=cart_item.product_id
                )
                .first()
            )

            if not product:

                messages.error(
                    request,
                    "A product in your cart is unavailable."
                )

                return redirect(
                    "cart:cart"
                )

            if not product.is_active:

                messages.error(
                    request,
                    f"{product.name} is currently unavailable."
                )

                return redirect(
                    "cart:cart"
                )

            if product.is_deleted:

                messages.error(
                    request,
                    f"{product.name} is no longer available."
                )

                return redirect(
                    "cart:cart"
                )

            if not product.category:

                messages.error(
                    request,
                    f"{product.name} is no longer available."
                )

                return redirect(
                    "cart:cart"
                )

            if (
                product.category.is_trashed
                or getattr(
                    product.category,
                    "is_blocked",
                    False
                )
            ):

                messages.error(
                    request,
                    f"{product.name} is no longer available."
                )

                return redirect(
                    "cart:cart"
                )

            available_quantity = product.quantity

        if available_quantity <= 0:

            if variant:

                messages.error(
                    request,
                    f"{product.name} "
                    f"({get_purchase_label(product, variant)}) "
                    f"is out of stock."
                )

            else:

                messages.error(
                    request,
                    f"{product.name} is out of stock."
                )

            return redirect(
                "cart:cart"
            )

        if cart_item.quantity > MAX_CART_QUANTITY:

            messages.error(
                request,
                f"Maximum allowed quantity is "
                f"{MAX_CART_QUANTITY}."
            )

            return redirect(
                "cart:cart"
            )

        if cart_item.quantity > available_quantity:

            if variant:

                messages.error(
                    request,
                    f"Only {available_quantity} unit(s) of "
                    f"{product.name} "
                    f"({get_purchase_label(product, variant)}) "
                    f"are available."
                )

            else:

                messages.error(
                    request,
                    f"Only {available_quantity} unit(s) of "
                    f"{product.name} are available."
                )

            return redirect(
                "cart:cart"
            )

        (
            original_total,
            item_discount,
            item_total,
            unit_price,
            unit_discount,
        ) = get_product_pricing(
            product,
            cart_item.quantity,
            variant,
        )

        subtotal += original_total
        discount_amount += item_discount

        validated_items.append(
            {
                "cart_item": cart_item,
                "product": product,
                "variant": variant,
                "price": unit_price,
                "discount": unit_discount,
                "item_total": item_total,
                "original_total": original_total,
            }
        )

    tax = Decimal("0.00")
    shipping_charge = Decimal("0.00")

    total_amount = (
        subtotal
        - discount_amount
        + tax
        + shipping_charge
    )

    order = Order.objects.create(

        user=request.user,

        address=address,

        payment_method=payment_method,

        status="Pending",

        subtotal=subtotal,

        discount=discount_amount,

        tax=tax,

        shipping_charge=shipping_charge,

        delivery_date=delivery_date,

        total_amount=total_amount,
    )

    for item in validated_items:

        cart_item = item["cart_item"]
        product = item["product"]
        variant = item["variant"]

        OrderItem.objects.create(

            order=order,

            product=product,

            product_name=product.name,

            variant=variant,

            discount=item["discount"],

            price=item["price"],

            quantity=cart_item.quantity,

            item_total=item["item_total"],

            status="Pending",


        )

        if variant:

            if variant.quantity < cart_item.quantity:

                raise ValueError(
                    f"Insufficient stock for {variant}"
                )

            variant.quantity -= cart_item.quantity

            variant.save(
                update_fields=[
                    "quantity",
                    "updated_at",
                ]
            )

        else:

            if product.quantity < cart_item.quantity:

                raise ValueError(
                    f"Insufficient stock for {product.name}"
                )

            product.quantity -= cart_item.quantity

            product.save(
                update_fields=[
                    "quantity",
                    "updated_at",
                ]
            )

    # Synchronize order status from its item statuses.
    update_status(order)

    Cart.objects.filter(
        user=request.user
    ).delete()

    request.session[
        "last_order_id"
    ] = order.id

    request.session.pop(
        "checkout_address_id",
        None,
    )

    request.session.pop(
        "checkout_payment_method",
        None,
    )

    request.session.pop(
        "checkout_delivery_date",
        None,
    )

    return redirect(
        "orders:order_success"
    )

# ============================================================
# ORDER SUCCESS
# ============================================================

@login_required
@never_cache
def order_success(request):

    order_id = request.session.get(
        "last_order_id"
    )

    if not order_id:

        return redirect(
            "orders:order_list"
        )

    order = (
        Order.objects
        .filter(
            id=order_id,
            user=request.user,
        )
        .select_related("address")
        .prefetch_related(
            "items__product__images",
            "items__variant__images",
        )
        .first()
    )

    if not order:

        messages.error(
            request,
            "Order not found."
        )

        return redirect(
            "orders:order_list"
        )

    for item in order.items.all():

        item.purchase_label = get_purchase_label(
            item.product,
            item.variant,
        )

        item.variant_label = item.purchase_label

    return render(
        request,
        "order_success.html",
        {
            "order": order,
        },
    )


# ============================================================
# DOWNLOAD INVOICE
# ============================================================

@login_required
def download_invoice(request, order_id):

    order = (
        Order.objects
        .filter(
            id=order_id,
            user=request.user,
        )
        .select_related(
            "address",
            "user",
        )
        .prefetch_related(
            "items__product",
            "items__variant",
        )
        .first()
    )

    if not order:

        messages.error(
            request,
            "Order not found."
        )

        return redirect(
            "orders:order_list"
        )

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Title"],
        fontSize=20,
        spaceAfter=10,
    )

    normal_style = ParagraphStyle(
        "InvoiceNormal",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
    )

    elements = []

    elements.append(
        Paragraph(
            f"Invoice - Order #{order.id}",
            title_style,
        )
    )

    elements.append(
        Spacer(1, 8)
    )

    elements.append(
        Paragraph(
            f"<b>Customer:</b> "
            f"{order.user.get_full_name() or order.user.username}",
            normal_style,
        )
    )

    elements.append(
        Paragraph(
            f"<b>Order Date:</b> "
            f"{order.created_at.strftime('%d-%m-%Y %H:%M')}",
            normal_style,
        )
    )

    elements.append(
        Paragraph(
            f"<b>Payment:</b> "
            f"{order.get_payment_method_display()}",
            normal_style,
        )
    )

    elements.append(
        Paragraph(
            f"<b>Status:</b> {order.status}",
            normal_style,
        )
    )

    elements.append(
        Spacer(1, 10)
    )

    address = order.address

    address_lines = []

    for field in [
        getattr(address, "name", None),
        getattr(address, "address_line1", None),
        getattr(address, "address_line2", None),
        getattr(address, "city", None),
        getattr(address, "state", None),
        getattr(address, "pincode", None),
        getattr(address, "phone", None),
    ]:

        if field:

            address_lines.append(
                str(field)
            )

    if address_lines:

        address_text = "<br/>".join(
            address_lines
        )

        elements.append(
            Paragraph(
                f"<b>Delivery Address:</b>"
                f"<br/>{address_text}",
                normal_style,
            )
        )

        elements.append(
            Spacer(1, 10)
        )

    table_data = [
        [
            "Product",
            "Qty",
            "Price",
            "Discount",
            "Total",
        ]
    ]

    for item in order.items.all():

        if item.is_cancelled or item.is_returned:
            continue

        product_name = item.product_name

        purchase_label = get_purchase_label(
            item.product,
            item.variant,
        )

        if purchase_label:

            product_name = (
                f"{product_name} "
                f"({purchase_label})"
            )

        table_data.append(
            [
                product_name,
                str(item.quantity),
                f"₹{item.price:.2f}",
                f"₹{item.discount:.2f}",
                f"₹{item.item_total:.2f}",
            ]
        )

    table = Table(
        table_data,
        colWidths=[
            75 * mm,
            18 * mm,
            28 * mm,
            28 * mm,
            28 * mm,
        ],
        repeatRows=1,
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.lightgrey,
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.black,
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey,
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold",
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
            ]
        )
    )

    elements.append(table)

    elements.append(
        Spacer(1, 12)
    )

    totals_data = [
        [
            "Subtotal",
            f"₹{order.subtotal:.2f}",
        ],
        [
            "Discount",
            f"- ₹{order.discount:.2f}",
        ],
        [
            "Tax",
            f"₹{order.tax:.2f}",
        ],
        [
            "Shipping",
            f"₹{order.shipping_charge:.2f}",
        ],
        [
            "Grand Total",
            f"₹{order.total_amount:.2f}",
        ],
    ]

    totals_table = Table(
        totals_data,
        colWidths=[
            140 * mm,
            37 * mm,
        ],
    )

    totals_table.setStyle(
        TableStyle(
            [
                (
                    "ALIGN",
                    (1, 0),
                    (1, -1),
                    "RIGHT",
                ),
                (
                    "FONTNAME",
                    (0, -1),
                    (-1, -1),
                    "Helvetica-Bold",
                ),
                (
                    "LINEABOVE",
                    (0, -1),
                    (-1, -1),
                    1,
                    colors.black,
                ),
            ]
        )
    )

    elements.append(
        totals_table
    )

    document.build(
        elements
    )

    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/pdf",
    )

    response[
        "Content-Disposition"
    ] = (
        f'attachment; filename="order_{order.id}_invoice.pdf"'
    )

    return response


# ============================================================
# ORDER LIST
# ============================================================

@login_required
@never_cache
def order_list(request):

    orders = (
        Order.objects
        .filter(user=request.user)
        .select_related("address")
        .prefetch_related(
            "items__product__images",
            "items__variant__images",
        )
        .order_by("-created_at")
    )

    search = request.GET.get(
        "search",
        ""
    ).strip()

    if search:

        orders = orders.filter(
            Q(id__icontains=search)
            | Q(items__product_name__icontains=search)
        ).distinct()

    selected_status = request.GET.get(
        "status",
        ""
    ).strip()

    valid_statuses = [
        "Pending",
        "Processing",
        "Shipped",
        "Partially Shipped",
        "Out for Delivery",
        "Delivered",
        "Partially Delivered",
        "Cancelled",
        "Returned",
    ]

    if selected_status in valid_statuses:

        if selected_status == "Cancelled":

            orders = orders.filter(
                items__status="Cancelled"
            ).distinct()

        elif selected_status == "Returned":

            orders = orders.filter(
                items__status="Returned"
            ).distinct()

        else:

            orders = orders.filter(
                status=selected_status
            )

    selected_sort = request.GET.get(
        "sort",
        "newest"
    ).strip()

    if selected_sort == "oldest":

        orders = orders.order_by(
            "created_at"
        )

    elif selected_sort == "total_high":

        orders = orders.order_by(
            "-total_amount",
            "-created_at",
        )

    elif selected_sort == "total_low":

        orders = orders.order_by(
            "total_amount",
            "-created_at",
        )

    else:

        selected_sort = "newest"

        orders = orders.order_by(
            "-created_at"
        )

    paginator = Paginator(
        orders,
        5
    )

    page_number = request.GET.get(
        "page"
    )

    page_obj = paginator.get_page(
        page_number
    )

    for order in page_obj:

        for item in order.items.all():

            item.display_status = (
                item.status or order.status
            )

            item.purchase_label = get_purchase_label(
                item.product,
                item.variant,
            )

            item.variant_label = (
                item.purchase_label
            )

            display_image = None

            if item.variant_id:

                variant_images = list(
                    item.variant.images.all()
                )

                display_image = next(
                    (
                        image
                        for image in variant_images
                        if image.image_type == "main"
                    ),
                    None
                )

                if (
                    not display_image
                    and variant_images
                ):

                    display_image = (
                        variant_images[0]
                    )

            if not display_image:

                if item.product.main_image:

                    display_image = (
                        item.product.main_image
                    )

                else:

                    product_images = list(
                        item.product.images.all()
                    )

                    if product_images:

                        display_image = (
                            product_images[0]
                        )

            item.display_image = (
                display_image
            )

    context = {

        "orders": page_obj,

        "page_obj": page_obj,

        "search": search,

        "selected_status": selected_status,

        "selected_sort": selected_sort,

        "status_choices": valid_statuses,
    }

    return render(
        request,
        "order_list.html",
        context,
    )
# ============================================================
# VIEW ORDER
# ============================================================

@login_required
@never_cache
def view_order(request):

    if request.method != "POST":

        return redirect(
            "orders:order_list"
        )

    order_id = request.POST.get(
        "order_id"
    )

    if not order_id:

        messages.error(
            request,
            "Order not found."
        )

        return redirect(
            "orders:order_list"
        )

    order = (
        Order.objects
        .filter(
            id=order_id,
            user=request.user,
        )
        .select_related(
            "address",
        )
        .prefetch_related(
            "items__product__images",
            "items__variant__images",
        )
        .first()
    )

    if not order:

        messages.error(
            request,
            "Order not found."
        )

        return redirect(
            "orders:order_list"
        )

    for item in order.items.all():

        if item.is_returned:

            item.display_status = "Returned"

        elif item.is_cancelled:

            item.display_status = "Cancelled"

        else:

            item.display_status = (
                getattr(
                    item,
                    "status",
                    order.status
                )
            )

        if item.variant_id:

            variant_images = list(
                item.variant.images.all()
            )

            main_variant_image = next(
                (
                    image
                    for image in variant_images
                    if image.image_type == "main"
                ),
                None
            )

            if main_variant_image:

                item.main_display_image = (
                    main_variant_image
                )

            elif variant_images:

                item.main_display_image = (
                    variant_images[0]
                )

            else:

                product_images = list(
                    item.product.images.all()
                )

                if item.product.main_image:

                    item.main_display_image = (
                        item.product.main_image
                    )

                elif product_images:

                    item.main_display_image = (
                        product_images[0]
                    )

                else:

                    item.main_display_image = None

            if variant_images:

                item.display_images = variant_images

            else:

                item.display_images = list(
                    item.product.images.all()
                )

            item.display_size = item.variant.size
            item.display_color = item.variant.color

        else:

            product_images = list(
                item.product.images.all()
            )

            item.display_images = product_images

            if item.product.main_image:

                item.main_display_image = (
                    item.product.main_image
                )

            elif product_images:

                item.main_display_image = (
                    product_images[0]
                )

            else:

                item.main_display_image = None

            item.display_size = item.product.size
            item.display_color = item.product.color

        item.original_price = (
            item.price + item.discount
        )

    # ========================================================
    # CANCELLATION
    # ========================================================

    cancellable_items = (
        order.items.filter(
            is_cancelled=False,
            is_returned=False,
        )
    )

    can_cancel_order = (
        order.status in [
            "Pending",
            "Processing",
            "Shipped",
            "Partially Shipped",
            "Out for Delivery",
        ]
        and cancellable_items.exists()
    )

    # ========================================================
    # RETURN
    # ========================================================

    returnable_items = (
        order.items.filter(
            is_cancelled=False,
            is_returned=False,
        )
    )

    can_return_order = (
        order.status == "Delivered"
        and returnable_items.exists()
    )

    return render(
        request,
        "view_order.html",
        {
            "order": order,
            "can_cancel_order": can_cancel_order,
            "can_return_order": can_return_order,
        }
    )


# ============================================================
# CANCEL ORDER ITEMS
# ============================================================

@login_required
@never_cache
def cancel_order(request):

    if request.method != "POST":

        return redirect(
            "orders:order_list"
        )

    order_id = request.POST.get(
        "order_id"
    )

    if not order_id:

        messages.error(
            request,
            "Order not found."
        )

        return redirect(
            "orders:order_list"
        )

    order = (
        Order.objects
        .filter(
            id=order_id,
            user=request.user
        )
        .prefetch_related(
            "items__product__images",
            "items__variant__images",
        )
        .first()
    )

    if not order:

        messages.error(
            request,
            "Order not found."
        )

        return redirect(
            "orders:order_list"
        )

    cancel_complete_order = (
        request.POST.get(
            "cancel_complete_order"
        ) == "yes"
    )

    selected_items = request.POST.getlist(
        "selected_items"
    )

    if cancel_complete_order:

        selected_items = list(
            order.items
            .filter(
                is_cancelled=False,
                is_returned=False,
            )
            .values_list(
                "id",
                flat=True
            )
        )

    if not selected_items:

        return render(
            request,
            "cancel.html",
            {
                "order": order,
                "items": order.items.all(),
            }
        )

    reason = request.POST.get(
        "cancellation_reason",
        ""
    ).strip()

    if not reason:

        messages.error(
            request,
            "Please select a cancellation reason."
        )

        return render(
            request,
            "cancel.html",
            {
                "order": order,
                "items": order.items.all(),
            }
        )

    # ========================================================
    # ATOMIC CANCELLATION
    # ========================================================

    with transaction.atomic():

        locked_order = (
            Order.objects
            .select_for_update()
            .filter(
                id=order_id,
                user=request.user
            )
            .first()
        )

        if not locked_order:

            messages.error(
                request,
                "Order not found."
            )

            return redirect(
                "orders:order_list"
            )

        if locked_order.status not in [
            "Pending",
            "Processing",
            "Shipped",
            "Partially Shipped",
            "Out for Delivery",
        ]:

            messages.error(
                request,
                "This order cannot be cancelled."
            )

            return redirect(
                "orders:order_list"
            )

        items = (
            OrderItem.objects
            .select_for_update()
            .filter(
                order=locked_order,
                id__in=selected_items,
                is_cancelled=False,
                is_returned=False,
            )
            .select_related(
                "product",
                "variant",
            )
        )

        if not items.exists():

            messages.error(
                request,
                "No valid items were selected."
            )

            return redirect(
                "orders:order_list"
            )

        for item in items:

            # ------------------------------------------------
            # Restore variant stock
            # ------------------------------------------------

            if item.variant:

                variant = (
                    ProductVariant.objects
                    .select_for_update()
                    .get(
                        id=item.variant_id
                    )
                )

                variant.quantity += item.quantity

                variant.save(
                    update_fields=[
                        "quantity",
                        "updated_at",
                    ]
                )

            # ------------------------------------------------
            # Restore base product stock
            # ------------------------------------------------

            else:

                product = (
                    Product.objects
                    .select_for_update()
                    .get(
                        id=item.product_id
                    )
                )

                product.quantity += item.quantity

                product.save(
                    update_fields=[
                        "quantity",
                        "updated_at",
                    ]
                )

            # ------------------------------------------------
            # Mark item as cancelled
            # ------------------------------------------------

            item.is_cancelled = True
            item.cancellation_reason = reason
            item.status = "Cancelled"

            item.save(
                update_fields=[
                    "is_cancelled",
                    "cancellation_reason",
                    "status",
                ]
            )

        # ----------------------------------------------------
        # Automatically calculate order status
        # ----------------------------------------------------

        update_status(locked_order)

    request.session[
        "last_cancelled_order_id"
    ] = locked_order.id

    return redirect(
        "orders:cancellation_success"
    )


# ============================================================
# CANCEL SUCCESS
# ============================================================

@login_required
@never_cache
def cancellation_success(request):

    order_id = request.session.get(
        "last_cancelled_order_id"
    )

    if not order_id:

        messages.error(
            request,
            "Order not found."
        )

        return redirect(
            "orders:order_list"
        )

    order = (
        Order.objects
        .filter(
            id=order_id,
            user=request.user,
        )
        .prefetch_related(
            "items__product__images",
            "items__variant__images",
        )
        .first()
    )

    if not order:

        messages.error(
            request,
            "Order not found."
        )

        request.session.pop(
            "last_cancelled_order_id",
            None
        )

        return redirect(
            "orders:order_list"
        )

    request.session.pop(
        "last_cancelled_order_id",
        None
    )

    return render(
        request,
        "cancellation_success.html",
        {
            "order": order,
        },
    )


# ============================================================
# RETURN ORDER ITEMS
# ============================================================

@login_required
@never_cache
@transaction.atomic
def return_order(request):

    if request.method != "POST":

        messages.error(
            request,
            "Invalid return request."
        )

        return redirect(
            "orders:order_list"
        )

    order_id = request.POST.get(
        "order_id"
    )

    if not order_id:

        messages.error(
            request,
            "Order not found."
        )

        return redirect(
            "orders:order_list"
        )

    order = (
        Order.objects
        .select_for_update()
        .filter(
            id=order_id,
            user=request.user,
        )
        .select_related(
            "address",
        )
        .first()
    )

    if not order:

        messages.error(
            request,
            "Order not found."
        )

        return redirect(
            "orders:order_list"
        )

    # ========================================================
    # ONLY DELIVERED ORDER CAN HAVE RETURNS
    # ========================================================

    if order.status != "Delivered":

        messages.error(
            request,
            "Only delivered products can be returned."
        )

        return redirect(
            "orders:order_list"
        )

    returnable_items = list(
        OrderItem.objects
        .filter(
            order=order,
            is_cancelled=False,
            is_returned=False,
        )
        .select_related(
            "product",
            "product__main_image",
            "variant",
        )
        .prefetch_related(
            "product__images",
            "variant__images",
        )
    )

    if not returnable_items:

        messages.error(
            request,
            "There are no products available for return."
        )

        return redirect(
            "orders:order_list"
        )

    # ========================================================
    # PREPARE DISPLAY IMAGES
    # ========================================================

    for item in returnable_items:

        item.main_display_image = None
        item.display_images = []

        if item.variant_id:

            variant_images = list(
                item.variant.images.all()
            )

            item.display_images = variant_images

            main_variant_image = next(
                (
                    image
                    for image in variant_images
                    if image.image_type == "main"
                ),
                None
            )

            if main_variant_image:

                item.main_display_image = (
                    main_variant_image
                )

            elif variant_images:

                item.main_display_image = (
                    variant_images[0]
                )

            else:

                product_images = list(
                    item.product.images.all()
                )

                if item.product.main_image:

                    item.main_display_image = (
                        item.product.main_image
                    )

                elif product_images:

                    item.main_display_image = (
                        product_images[0]
                    )

                item.display_images = product_images

        else:

            product_images = list(
                item.product.images.all()
            )

            item.display_images = product_images

            if item.product.main_image:

                item.main_display_image = (
                    item.product.main_image
                )

            elif product_images:

                item.main_display_image = (
                    product_images[0]
                )

    selected_items = request.POST.getlist(
        "selected_items"
    )

    if not selected_items:

        return render(
            request,
            "return.html",
            {
                "order": order,
                "returnable_items": returnable_items,
            },
        )

    return_reason = request.POST.get(
        "return_reason",
        ""
    ).strip()

    if not return_reason:

        messages.error(
            request,
            "Please select a return reason."
        )

        return render(
            request,
            "return.html",
            {
                "order": order,
                "returnable_items": returnable_items,
            },
        )

    returned_any = False

    for item_id in selected_items:

        item = (
            OrderItem.objects
            .select_for_update()
            .filter(
                id=item_id,
                order=order,
                is_cancelled=False,
                is_returned=False,
            )
            .select_related(
                "product",
                "variant",
            )
            .first()
        )

        if not item:
            continue

        # ----------------------------------------------------
        # Restore variant stock
        # ----------------------------------------------------

        if item.variant_id:

            variant = (
                ProductVariant.objects
                .select_for_update()
                .filter(
                    id=item.variant_id,
                    product_id=item.product_id,
                )
                .first()
            )

            if variant:

                variant.quantity += item.quantity

                variant.save(
                    update_fields=[
                        "quantity",
                        "updated_at",
                    ]
                )

        # ----------------------------------------------------
        # Restore base product stock
        # ----------------------------------------------------

        else:

            product = (
                Product.objects
                .select_for_update()
                .filter(
                    id=item.product_id
                )
                .first()
            )

            if product:

                product.quantity += item.quantity

                product.save(
                    update_fields=[
                        "quantity",
                        "updated_at",
                    ]
                )

        # ----------------------------------------------------
        # Mark item as returned
        # ----------------------------------------------------

        item.is_returned = True
        item.return_reason = return_reason
        item.status = "Returned"

        item.save(
            update_fields=[
                "is_returned",
                "return_reason",
                "status",
            ]
        )

        returned_any = True

    if not returned_any:

        messages.error(
            request,
            "No valid products were selected for return."
        )

        return render(
            request,
            "return.html",
            {
                "order": order,
                "returnable_items": returnable_items,
            },
        )

    # ========================================================
    # AUTOMATICALLY CALCULATE ORDER STATUS
    # ========================================================

    update_status(order)

    request.session[
        "return_success_order_id"
    ] = order.id

    messages.success(
        request,
        "Selected product(s) returned successfully."
    )

    return redirect(
        "orders:return_success"
    )


# ============================================================
# RETURN SUCCESS
# ============================================================

@login_required
@never_cache
def return_success(request):

    order_id = request.session.pop(
        "return_success_order_id",
        None,
    )

    if not order_id:

        messages.error(
            request,
            "Return information is unavailable."
        )

        return redirect(
            "orders:order_list"
        )

    order = (
        Order.objects
        .filter(
            id=order_id,
            user=request.user,
        )
        .prefetch_related(
            "items__product__images",
            "items__variant__images",
        )
        .first()
    )

    if not order:

        messages.error(
            request,
            "Order not found."
        )

        return redirect(
            "orders:order_list"
        )

    return render(
        request,
        "return_success.html",
        {
            "order": order,
        },
    )