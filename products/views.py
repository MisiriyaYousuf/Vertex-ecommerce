from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.db.models import Exists, OuterRef, Q, Prefetch, Min, Sum, Value, IntegerField, Subquery
from django.db.models.functions import Coalesce
from decimal import Decimal, InvalidOperation
from cart.views import MAX_CART_QUANTITY
from cart.models import Cart, Wishlist
from customadmin.models import Category
from .models import Product, ProductVariant,ProductImage,ProductVariantImage
from offers.services import add_pricing


active_variant_stock = ProductVariant.objects.filter(
    product_id=OuterRef("pk"), is_active=True
).values("product_id").annotate(total=Sum("quantity")).values("total")
active_variant_price = ProductVariant.objects.filter(
    product_id=OuterRef("pk"), is_active=True
).values("product_id").annotate(minimum=Min("sale_price")).values("minimum")


@never_cache
@login_required
def products(request):

    available_variant = ProductVariant.objects.filter(
    product=OuterRef("pk"),
    is_active=True,
    quantity__gt=0,
    )

    product_list = (
        Product.objects
        .filter(
            is_active=True,
            is_deleted=False,
            category__is_trashed=False,
        )
        .annotate(
            has_stock=Exists(available_variant),
            total_stock=Coalesce(Subquery(active_variant_stock), Value(0), output_field=IntegerField()),
            minimum_price=Subquery(active_variant_price),
        )
        .select_related(
            "category",
        )
        .prefetch_related(
            "images",
            "variants__images",
        )
    )
    search_query = request.GET.get(
        "search",
        "",
    ).strip()

    if search_query:

        product_list = product_list.filter(
            Q(name__icontains=search_query)
            |
            Q(description__icontains=search_query)
            |
            Q(variants__color__icontains=search_query)
            |
            Q(variants__size__icontains=search_query)
            |
            Q(variants__product_code__icontains=search_query)
            |
            Q(category__name__icontains=search_query)
            |
            Q(brand__icontains=search_query)
        )

    categories = (
        Category.objects
        .filter(
            is_trashed=False,
        )
        .order_by("name")
    )
    selected_category = request.GET.get("category", "").strip()
    selected_category_name = request.GET.get("category_name", "").strip()

    if selected_category_name:
        category = categories.filter(name__iexact=selected_category_name).first()
        if category:
            selected_category = str(category.id)
            product_list = product_list.filter(category_id=category.id)
        else:
            product_list = product_list.none()
    elif selected_category:
        product_list = product_list.filter(category_id=selected_category)

    brands = list(
        Product.objects.filter(
            is_active=True,
            is_deleted=False,
            category__is_trashed=False,
        ).exclude(brand="").values_list("brand", flat=True).distinct().order_by("brand")
    )
    selected_brand = request.GET.get("brand", "").strip()
    if selected_brand:
        product_list = product_list.filter(brand__iexact=selected_brand)

    min_price = request.GET.get(
        "min_price",
        "",
    ).strip()


    max_price = request.GET.get(
        "max_price",
        "",
    ).strip()


    price_filter = Q()
    has_price_filter = False
    try:
        if min_price:
            price_filter &= Q(variants__sale_price__gte=Decimal(min_price))
            has_price_filter = True
        if max_price:
            price_filter &= Q(variants__sale_price__lte=Decimal(max_price))
            has_price_filter = True
    except (InvalidOperation, ValueError, TypeError):
        has_price_filter = False
    if has_price_filter:
        product_list = product_list.filter(price_filter)

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
    selected_sort = request.GET.get(
        "sort",
        "newest",
    ).strip()


    if selected_sort == "price_low":

        product_list = product_list.order_by("minimum_price", "id")


    elif selected_sort == "price_high":

        product_list = product_list.order_by("-minimum_price", "-id")


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
            "-updated_at",
            "-id",
        )

    product_list = product_list.distinct()

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

    wishlisted_product_ids = set(
        Wishlist.objects.filter(
            user=request.user,
            product_id__in=[product.id for product in products_page],
        ).values_list("product_id", flat=True)
    )
    cart_product_ids = set(
        Cart.objects.filter(
            user=request.user,
            product_id__in=[product.id for product in products_page],
        ).values_list("product_id", flat=True)
    )

    for product in products_page:
        priced_variants = []
        for variant in product.variants.all():
            add_pricing(product, variant)
            if variant.is_active:
                priced_variants.append(variant)
        product.display_variant = min(priced_variants, key=lambda variant: variant.pricing.unit_price) if priced_variants else None
        product.pricing = product.display_variant.pricing if product.display_variant else None
    context = {

        "products": products_page,

        "wishlisted_product_ids": wishlisted_product_ids,

        "cart_product_ids": cart_product_ids,

        "categories": categories,

        "brands": brands,

        "selected_brand": selected_brand,

        "selected_category": selected_category,

        "min_price": min_price,

        "max_price": max_price,

        "selected_stock": selected_stock,

        "selected_sort": selected_sort,

        "search_query": search_query,

    }


    return render(
        request,
        "product.html",
        context,
    )

@never_cache
@login_required
def products_details(request, name):

    product = (
        Product.objects
        .filter(
            name=name,
            is_active=True,
            is_deleted=False,
        )
        .select_related(
            "category",
        )
        .prefetch_related(
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
        )
        .prefetch_related(
            "images",
        )
        .distinct()[:8]
    )

    for variant in variants:
        add_pricing(product, variant)
    product.display_variant = min(variants, key=lambda variant: variant.pricing.unit_price) if variants else None
    product.pricing = product.display_variant.pricing if product.display_variant else None
    for related_product in related_products:
        related_variants = [v for v in related_product.variants.all() if v.is_active]
        for variant in related_variants:
            add_pricing(related_product, variant)
        related_product.display_variant = min(related_variants, key=lambda variant: variant.pricing.unit_price) if related_variants else None
        related_product.pricing = related_product.display_variant.pricing if related_product.display_variant else None

    return render(
        request,
        "products_details.html",
        {
            "product": product,

            "is_wishlisted": Wishlist.objects.filter(
                user=request.user,
                product=product,
            ).exists(),

            "variants": variants,

            "related_products": related_products,

            "max_cart_quantity": MAX_CART_QUANTITY,
        }
    )
