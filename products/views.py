from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.db.models import Exists, OuterRef, Q,Prefetch
from cart.views import MAX_CART_QUANTITY
from customadmin.models import Category
from .models import Product, ProductVariant,ProductImage,ProductVariantImage


@never_cache
@login_required
def products(request):

    # =========================================================
    # AVAILABLE VARIANT
    # =========================================================

    available_variant = ProductVariant.objects.filter(
        product=OuterRef("pk"),
        is_active=True,
        quantity__gt=0,
    )


    # =========================================================
    # PRODUCT QUERY
    #
    # IMPORTANT:
    # We no longer depend on Product.main_image.
    #
    # The main image is taken from ProductImage where:
    # image_type = "main"
    # =========================================================

    main_images = ProductImage.objects.filter(
        image_type="main"
    )


    product_list = (
        Product.objects
        .filter(
            is_active=True,
            is_deleted=False,
            category__is_trashed=False,
        )
        .annotate(
            has_stock=(
                Q(quantity__gt=0)
                | Exists(available_variant)
            ),
        )
        .select_related(
            "category",
        )
        .prefetch_related(
            Prefetch(
                "images",
                queryset=main_images,
                to_attr="main_product_images",
            ),
            "variants__images",
        )
    )


    # =========================================================
    # CATEGORIES
    # =========================================================

    categories = (
        Category.objects
        .filter(
            is_trashed=False,
        )
        .order_by("name")
    )


    # =========================================================
    # CATEGORY FILTER
    # =========================================================

    selected_category = request.GET.get(
        "category",
        "",
    ).strip()


    if selected_category:

        product_list = product_list.filter(
            category_id=selected_category,
        )


    # =========================================================
    # MIN PRICE
    # =========================================================

    min_price = request.GET.get(
        "min_price",
        "",
    ).strip()


    if min_price:

        try:

            product_list = product_list.filter(
                Q(
                    discount_price__gte=min_price,
                )
                |
                Q(
                    discount_price__isnull=True,
                    sale_price__gte=min_price,
                )
            )

        except (ValueError, TypeError):

            pass


    # =========================================================
    # MAX PRICE
    # =========================================================

    max_price = request.GET.get(
        "max_price",
        "",
    ).strip()


    if max_price:

        try:

            product_list = product_list.filter(
                Q(
                    discount_price__lte=max_price,
                )
                |
                Q(
                    discount_price__isnull=True,
                    sale_price__lte=max_price,
                )
            )

        except (ValueError, TypeError):

            pass


    # =========================================================
    # STOCK FILTER
    #
    # BASE PRODUCT:
    # quantity > 0
    #
    # OR
    #
    # ACTIVE VARIANT:
    # quantity > 0
    # =========================================================

    selected_stock = request.GET.get(
        "stock",
        "",
    ).strip()


    if selected_stock == "in_stock":

        product_list = product_list.filter(
            has_stock=True,
        )


    elif selected_stock == "out_of_stock":

        product_list = product_list.filter(
            has_stock=False,
        )


    # =========================================================
    # SORT
    # =========================================================

    selected_sort = request.GET.get(
        "sort",
        "newest",
    ).strip()


    if selected_sort == "price_low":

        product_list = product_list.order_by(
            "discount_price",
            "sale_price",
        )


    elif selected_sort == "price_high":

        product_list = product_list.order_by(
            "-discount_price",
            "-sale_price",
        )


    elif selected_sort == "name_asc":

        product_list = product_list.order_by(
            "name",
        )


    elif selected_sort == "name_desc":

        product_list = product_list.order_by(
            "-name",
        )


    else:

        product_list = product_list.order_by(
            "-id",
        )


    # =========================================================
    # PAGINATION
    # =========================================================

    paginator = Paginator(
        product_list,
        6,
    )


    page_number = request.GET.get(
        "page",
    )


    products_page = paginator.get_page(
        page_number,
    )


    # =========================================================
    # CONTEXT
    # =========================================================

    context = {

        "products": products_page,

        "categories": categories,

        "selected_category": selected_category,

        "min_price": min_price,

        "max_price": max_price,

        "selected_stock": selected_stock,

        "selected_sort": selected_sort,

    }


    return render(
        request,
        "product.html",
        context,
    )

@never_cache
@login_required
def products_details(request, name):

    # =========================================================
    # PRODUCT
    # =========================================================

    try:

        product = (
            Product.objects
            .filter(
                name=name,
                is_active=True,
                is_deleted=False,
            )
            .select_related(
                "category",
                "main_image",
            )
            .prefetch_related(
                Prefetch(
                    "images",
                    queryset=ProductImage.objects.filter(
                        image_type="main"
                    ).order_by(
                        "position",
                        "id",
                    ),
                    to_attr="main_product_images",
                ),
                Prefetch(
                    "images",
                    queryset=ProductImage.objects.all().order_by(
                        "position",
                        "id",
                    ),
                ),
                Prefetch(
                    "variants__images",
                    queryset=ProductVariantImage.objects.all().order_by(
                        "position",
                        "id",
                    ),
                ),
            )
            .get()
        )

    except Product.DoesNotExist:

        return render(
            request,
            "products_details.html",
            {
                "product": None,
                "message": "Product not found.",
            }
        )

    # =========================================================
    # IMPORTANT:
    # USE THE PRODUCT'S MAIN IMAGE FIELD IF AVAILABLE.
    #
    # IF main_image IS NULL BUT A ProductImage WITH
    # image_type='main' EXISTS, USE THAT IMAGE.
    #
    # This fixes the situation where the image was uploaded
    # correctly but Product.main_image was not assigned.
    # =========================================================

    if (
        not product.main_image
        and getattr(product, "main_product_images", None)
    ):

        if product.main_product_images:

            product.main_image = (
                product.main_product_images[0]
            )

    # =========================================================
    # ACTIVE VARIANTS
    # =========================================================

    variants = (
        product.variants
        .filter(
            is_active=True,
        )
        .prefetch_related(
            Prefetch(
                "images",
                queryset=ProductVariantImage.objects.all().order_by(
                    "position",
                    "id",
                ),
            )
        )
    )

    # =========================================================
    # RELATED PRODUCTS
    # =========================================================

    related_products = (
        Product.objects
        .filter(
            category=product.category,
            is_active=True,
            is_deleted=False,
        )
        .exclude(
            id=product.id,
        )
        .select_related(
            "category",
            "main_image",
        )
        .prefetch_related(
            Prefetch(
                "images",
                queryset=ProductImage.objects.filter(
                    image_type="main"
                ).order_by(
                    "position",
                    "id",
                ),
                to_attr="main_product_images",
            ),
            Prefetch(
                "images",
                queryset=ProductImage.objects.all().order_by(
                    "position",
                    "id",
                ),
            ),
        )
        .distinct()[:8]
    )

    # =========================================================
    # FIX RELATED PRODUCT MAIN IMAGES
    # =========================================================

    for related_product in related_products:

        if (
            not related_product.main_image
            and getattr(
                related_product,
                "main_product_images",
                None,
            )
        ):

            if related_product.main_product_images:

                related_product.main_image = (
                    related_product.main_product_images[0]
                )

    # =========================================================
    # CONTEXT
    # =========================================================

    return render(
        request,
        "products_details.html",
        {
            "product": product,

            "variants": variants,

            "related_products": related_products,

            "max_cart_quantity": MAX_CART_QUANTITY,
        }
    )