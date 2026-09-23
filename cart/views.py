from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from products.models import Product, ProductVariant
from .models import Cart, Wishlist

MAX_CART_QUANTITY = 5

@never_cache
@login_required
def cart_view(request):

    cart_items = ( Cart.objects .filter(user=request.user)
        .select_related(
            "product",
            "product__category",
            "variant",
        )
        .prefetch_related(
            "product__images",
            "variant__images",
        )
    )
    total_items = sum(
        item.quantity
        for item in cart_items
    )

    cart_total = 0
    original_total = 0

    has_invalid_items = False
    has_out_of_stock_items = False
    has_exceeded_stock_items = False

    for item in cart_items:

        item.is_invalid = False
        item.is_out_of_stock = False
        item.has_exceeded_stock = False

        item.discount_percentage = 0

        item.unit_price = 0
        item.original_unit_price = 0

        item.subtotal = 0
        item.original_subtotal = 0
        item.discount_amount = 0

        product = item.product
        variant = item.variant

        if not product:

            item.is_invalid = True
            has_invalid_items = True

            continue


        if (
            not product.is_active
            or product.is_deleted
            or getattr(product, "is_blocked", False)
            or not product.category
            or product.category.is_trashed
            or getattr(product.category, "is_blocked", False)
        ):

            item.is_invalid = True
            has_invalid_items = True


        if variant:

            item.purchase_source = "variant"


            if not variant.is_active:

                item.is_invalid = True
                has_invalid_items = True

            

            stock_quantity = variant.quantity
            sale_price = variant.sale_price
            discount_price = variant.discount_price

        else:

            item.purchase_source = "product"
            stock_quantity = product.quantity
            sale_price = product.sale_price
            discount_price = product.discount_price

        if stock_quantity <= 0:

            item.is_out_of_stock = True
            has_out_of_stock_items = True

        elif item.quantity > stock_quantity:

            item.has_exceeded_stock = True
            has_exceeded_stock_items = True

        if discount_price is not None:

            selling_price = discount_price
            mrp = sale_price

            discount_per_item = (
                mrp - selling_price
            )

            if mrp > 0:

                item.discount_percentage = round(
                    (discount_per_item / mrp) * 100
                )

        else:

            selling_price = sale_price
            mrp = sale_price

            discount_per_item = 0

        item.unit_price = selling_price
        item.original_unit_price = mrp

        item.subtotal = (
            selling_price * item.quantity
        )

        item.original_subtotal = (
            mrp * item.quantity
        )

        item.discount_amount = (
            discount_per_item * item.quantity
        )

        cart_total += item.subtotal

        original_total += item.original_subtotal

    discount_amount = (
        original_total - cart_total
    )

    shipping_charge = 0

    grand_total = (
        cart_total + shipping_charge
    )

    return render(
        request,
        "cart.html",
        {
            "cart_items": cart_items,

            "total_items": total_items,

            "cart_total": cart_total,

            "original_total": original_total,

            "discount_amount": discount_amount,

            "shipping_charge": shipping_charge,

            "grand_total": grand_total,

            "has_invalid_items": has_invalid_items,

            "has_out_of_stock_items": (
                has_out_of_stock_items
            ),

            "has_exceeded_stock_items": (
                has_exceeded_stock_items
            ),

            "MAX_CART_QUANTITY": MAX_CART_QUANTITY,
        }
    )

@never_cache
@login_required
@transaction.atomic
def add_to_cart(request):

    if request.method != "POST":

        return redirect(
            "products:products"
        )

    product_id = request.POST.get(
        "product_id"
    )

    variant_id = request.POST.get(
        "variant_id"
    )

    if not product_id:

        messages.error(
            request,
            "Product is required."
        )

        return redirect(
            "products:products"
        )

    product = (
        Product.objects
        .filter(
            id=product_id,
            is_active=True,
            is_deleted=False,
            category__is_trashed=False,
        )
        .select_related(
            "category"
        )
        .first()
    )

    if not product:

        messages.error(
            request,
            "Product is currently unavailable."
        )

        return redirect(
            "products:products"
        )

    if not product.category:

        messages.error(
            request,
            "This product is currently unavailable."
        )

        return redirect(
            "products:products_details",
            product.name
        )

    if product.category.is_trashed:

        messages.error(
            request,
            "This product category is currently unavailable."
        )

        return redirect(
            "products:products_details",
            product.name
        )

    if getattr(
        product.category,
        "is_blocked",
        False
    ):

        messages.error(
            request,
            "This product category is currently unavailable."
        )

        return redirect(
            "products:products_details",
            product.name
        )

    variant = None

    if variant_id:

        variant = (
            ProductVariant.objects
            .filter(
                id=variant_id,
                product=product,
                is_active=True,
            )
            .first()
        )

        if not variant:

            messages.error(
                request,
                "Selected product variant is not available."
            )

            return redirect(
                "products:products_details",
                product.name
            )

        if variant.quantity <= 0:

            messages.error(
                request,
                "Selected variant is out of stock."
            )

            return redirect(
                "products:products_details",
                product.name
            )

        available_quantity = variant.quantity

    else:

        if product.quantity <= 0:

            messages.error(
                request,
                "This product is out of stock."
            )

            return redirect(
                "products:products_details",
                product.name
            )

        available_quantity = product.quantity

    cart_item = (
        Cart.objects
        .filter(
            user=request.user,
            product=product,
            variant=variant,
        )
        .first()
    )

    if cart_item:

        if cart_item.quantity >= MAX_CART_QUANTITY:

            if variant:

                messages.warning(
                    request,
                    f"You can add a maximum of "
                    f"{MAX_CART_QUANTITY} items of this variant."
                )

            else:

                messages.warning(
                    request,
                    f"You can add a maximum of "
                    f"{MAX_CART_QUANTITY} items of this product."
                )

            return redirect(
                "cart:cart"
            )

        if cart_item.quantity >= available_quantity:

            messages.warning(
                request,
                "The selected item is not available in the requested quantity."
            )

            return redirect(
                "cart:cart"
            )

        cart_item.quantity += 1

        cart_item.save(
            update_fields=[
                "quantity"
            ]
        )

        messages.success(
            request,
            "Product quantity increased."
        )

    else:

        Cart.objects.create(
            user=request.user,
            product=product,
            variant=variant,
            quantity=1,
        )

        Wishlist.objects.filter(
            user=request.user,
            product=product,
        ).delete()

        if variant:

            messages.success(
                request,
                "Product variant added to cart."
            )

        else:

            messages.success(
                request,
                "Product added to cart."
            )

    return redirect(
        "cart:cart"
    )

@never_cache
@login_required
@transaction.atomic
def increment_cart(request):

    if request.method != "POST":

        return redirect(
            "cart:cart"
        )
    
    cart_id = request.POST.get(
        "cart_id"
    )

    if not cart_id:

        messages.error(
            request,
            "Cart item not found."
        )

        return redirect(
            "cart:cart"
        )

    cart_item = (
        Cart.objects
        .filter(
            id=cart_id,
            user=request.user
        )
        .select_related(
            "product",
            "product__category",
            "variant"
        )
        .first()
    )

    if not cart_item:

        messages.error(
            request,
            "Cart item not found."
        )

        return redirect(
            "cart:cart"
        )

    product = cart_item.product

    variant = cart_item.variant
    if not product:

        messages.error(
            request,
            "This cart item is no longer available."
        )

        return redirect(
            "cart:cart"
        )

    if (
        not product.is_active
        or product.is_deleted
        or getattr(
            product,
            "is_blocked",
            False
        )
    ):

        messages.error(
            request,
            "This product is no longer available."
        )

        return redirect(
            "cart:cart"
        )

    if not product.category:

        messages.error(
            request,
            "This product is no longer available."
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
            "This product category is no longer available."
        )

        return redirect(
            "cart:cart"
        )

    if variant:

        if not variant.is_active:

            messages.error(
                request,
                "This product variant is no longer available."
            )

            return redirect(
                "cart:cart"
            )

        available_quantity = variant.quantity

        if available_quantity <= 0:

            messages.error(
                request,
                "This variant is out of stock."
            )

            return redirect(
                "cart:cart"
            )

        if cart_item.quantity >= MAX_CART_QUANTITY:

            messages.warning(
                request,
                f"You can add a maximum of "
                f"{MAX_CART_QUANTITY} items of this variant."
            )

            return redirect(
                "cart:cart"
            )

    else:

        available_quantity = product.quantity
        if available_quantity <= 0:

            messages.error(
                request,
                "This product is out of stock."
            )

            return redirect(
                "cart:cart"
            )

        if cart_item.quantity >= MAX_CART_QUANTITY:

            messages.warning(
                request,
                f"You can add a maximum of "
                f"{MAX_CART_QUANTITY} items of this product."
            )

            return redirect(
                "cart:cart"
            )

    if cart_item.quantity >= available_quantity:

        messages.warning(
            request,
            "The selected item is not available in the requested quantity."
        )

        return redirect(
            "cart:cart"
        )

    cart_item.quantity += 1

    cart_item.save(
        update_fields=[
            "quantity"
        ]
    )

    messages.success(
        request,
        "Quantity increased."
    )

    return redirect(
        "cart:cart"
    )

@never_cache
@login_required
@transaction.atomic
def decrement_cart(request):

    if request.method != "POST":

        return redirect(
            "cart:cart"
        )

    cart_id = request.POST.get(
        "cart_id"
    )

    if not cart_id:

        messages.error(
            request,
            "Cart item not found."
        )

        return redirect(
            "cart:cart"
        )

    cart_item = (
        Cart.objects
        .filter(
            id=cart_id,
            user=request.user
        )
        .first()
    )

    if not cart_item:

        messages.error(
            request,
            "Cart item not found."
        )

        return redirect(
            "cart:cart"
        )

    if cart_item.quantity > 1:

        cart_item.quantity -= 1

        cart_item.save(
            update_fields=[
                "quantity"
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
            "Product removed from cart."
        )

    return redirect(
        "cart:cart"
    )

@never_cache
@login_required
def remove_from_cart(request):

    if request.method != "POST":

        return redirect(
            "cart:cart"
        )

    item_id = request.POST.get(
        "item_id"
    )

    if not item_id:

        messages.error(
            request,
            "Cart item not found."
        )

        return redirect(
            "cart:cart"
        )

    cart_item = (
        Cart.objects
        .filter(
            id=item_id,
            user=request.user
        )
        .first()
    )

    if cart_item:

        cart_item.delete()

        messages.success(
            request,
            "Product removed from cart."
        )

    else:

        messages.error(
            request,
            "Cart item not found."
        )

    return redirect(
        "cart:cart"
    )

@never_cache
@login_required
def add_to_wishlist(request):

    if request.method != "POST":

        return redirect(
            "cart:cart"
        )

    product_id = request.POST.get(
        "product_id"
    )

    if not product_id:

        messages.error(
            request,
            "Invalid product."
        )

        return redirect(
            "cart:cart"
        )

    product = (
        Product.objects
        .filter(
            id=product_id
        )
        .first()
    )

    if not product:

        messages.error(
            request,
            "Product not found."
        )

        return redirect(
            "cart:cart"
        )


    Wishlist.objects.get_or_create(
        user=request.user,
        product=product
    )

    Cart.objects.filter(
        user=request.user,
        product=product
    ).delete()

    messages.success(
        request,
        "Product added to wishlist."
    )

    return redirect(
        "cart:wishlist_view"
    )

@never_cache
@login_required
def wishlist_view(request):

    wishlist_items = (
        Wishlist.objects
        .filter(
            user=request.user
        )
        .select_related(
            "product",
            "product__category"
        )
    )

    cart_product_ids = (
        Cart.objects
        .filter(
            user=request.user
        )
        .values_list(
            "product_id",
            flat=True
        )
    )

    wishlist_items = wishlist_items.exclude(
        product_id__in=cart_product_ids
    )

    return render(
        request,
        "wishlist.html",
        {
            "wishlist_items": wishlist_items
        }
    )

@never_cache
@login_required
def remove_from_wishlist(request):

    if request.method != "POST":

        return redirect(
            "cart:wishlist_view"
        )

    product_id = request.POST.get(
        "product_id"
    )

    if product_id:

        Wishlist.objects.filter(
            user=request.user,
            product_id=product_id
        ).delete()

        messages.success(
            request,
            "Product removed from wishlist."
        )

    return redirect(
        "cart:wishlist_view"
    )