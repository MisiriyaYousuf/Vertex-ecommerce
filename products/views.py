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
            has_stock=(
                Q(quantity__gt=0)
                | Exists(available_variant)
            ),
        )
        .select_related(
            "category",
            "main_image",
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
            Q(product_code__icontains=search_query)
            |
            Q(color__icontains=search_query)
            |
            Q(size__icontains=search_query)
            |
            Q(category__name__icontains=search_query)
        )

    categories = (
        Category.objects
        .filter(
            is_trashed=False,
        )
        .order_by("name")
    )
    selected_category = request.GET.get(
        "category",
        "",
    ).strip()

    if selected_category:

        product_list = product_list.filter(
            category_id=selected_category,
        )

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
    context = {

        "products": products_page,

        "categories": categories,

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
            "main_image",
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
            "main_image",
        )
        .prefetch_related(
            "images",
        )
        .distinct()[:8]
    )
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