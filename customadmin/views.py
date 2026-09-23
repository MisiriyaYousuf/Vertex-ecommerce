from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed
from django.contrib.auth import logout
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.utils import timezone
from .models import Category
from django.core.paginator import Paginator
from users.models import UserProfile
from .forms import CategoryForm
from django.db import transaction
from products.models import (Product,ProductImage,ProductVariant,ProductVariantImage,)
from .forms import ProductForm,ProductVariantForm
from django.http import JsonResponse
from orders.models import Order, OrderItem
from django.db.models import Q,F,Sum,Value,Prefetch,Count
from django.db.models.functions import Coalesce
from django.db.models import Sum

@login_required
@never_cache
def dashboard(request):

    user_count = UserProfile.objects.filter(
            user__is_superuser=False
        ).count()

    product_count = Product.objects.filter(
        is_active=True,
        is_deleted=False
    ).count()

    category_count = Category.objects.filter(
        is_trashed=False
    ).count()

    order_count = Order.objects.count()

    return_count = OrderItem.objects.filter(
        is_returned=True
    ).count()

    total_sales = Order.objects.exclude(
        status="Cancelled"
    ).aggregate(
        total=Sum("total_amount")
    )["total"] or 0

    context = {
        "user_count": user_count,
        "product_count": product_count,
        "category_count": category_count,
        "order_count": order_count,
        "return_count": return_count,
        "total_sales": total_sales,
    }

    return render(
        request,
        "dashboard.html",
        context
    )

@never_cache
@login_required
def user_management(request):
    if request.user.is_superuser:

        search = request.GET.get("search", "").strip()

        profiles = (
            UserProfile.objects
            .filter(user__is_superuser=False)
            .select_related("user")
        )

        if search:
            profiles = profiles.filter(
                Q(user__username__icontains=search)
                | Q(user__email__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(phone__icontains=search)
            )

        profiles = profiles.order_by("-user__date_joined")

        total_users = UserProfile.objects.filter(
            user__is_superuser=False
        ).count()

        paginator = Paginator(profiles, 2)
        page_number = request.GET.get("page")
        profiles = paginator.get_page(page_number)

        return render(
            request,
            "user_manage.html",
            {
                "profiles": profiles,
                "search": search,
                "total_users": total_users,
            },
        )

@never_cache
@login_required
def block_user(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    profile_id = request.POST.get("profile_id")

    profile = UserProfile.objects.filter(
        id=profile_id,
        user__is_superuser=False
    ).first()

    if not profile:
        messages.error(request, "User profile not found.")
        return redirect("customadmin:user_management")

    user = profile.user

    profile.blocked = True
    profile.save(update_fields=["blocked"])

    user.is_active = False
    user.save(update_fields=["is_active"])

    messages.success(
        request,
        f"{user.username} has been blocked successfully."
    )

    return redirect("customadmin:user_management")

@never_cache
@login_required
def unblock_user(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    profile_id = request.POST.get("profile_id")

    profile = UserProfile.objects.filter(
        id=profile_id,
        user__is_superuser=False
    ).first()

    if not profile:
        messages.error(request, "User profile not found.")
        return redirect("customadmin:user_management")

    user = profile.user

    profile.blocked = False
    profile.save(update_fields=["blocked"])

    user.is_active = True
    user.save(update_fields=["is_active"])

    messages.success(
        request,
        f"{user.username} has been unblocked successfully."
    )

    return redirect("customadmin:user_management")


@never_cache
@login_required
def category_management(request):
    search = request.GET.get("search","").strip()
    categories = Category.objects.filter(is_trashed=False).order_by("name")
    if search:
        categories = categories.filter(
            Q(name__icontains=search)
        )
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request,"Category added successfully.")
            return redirect("customadmin:category_management")
    else:
        form = CategoryForm()
    return render(request,"category_manage.html",{ "categories": categories, "form": form, "search": search, })

def edit_category(request):

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    category_id = request.POST.get("category_id")

    category = Category.objects.filter(
        id=category_id,
        is_trashed=False
    ).first()

    if not category:
        messages.error(
            request,
            "Category not found."
        )

        return redirect(
            "customadmin:category_management"
        )

    form = CategoryForm(
        request.POST,
        instance=category
    )

    if form.is_valid():

        form.save()

        messages.success(
            request,
            "Category updated successfully."
        )

        return redirect(
            "customadmin:category_management"
        )
    categories = Category.objects.filter(
        is_trashed=False
    ).order_by("-id")


    return render(
        request,
        "category_manage.html",
        {
            "categories": categories,
            "form": form,
            "category": category,
            "edit_category_id": category.id,
        }
    )

@never_cache
@login_required
def delete_category(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    category_id = request.POST.get("category_id")
    category = Category.objects.filter(id=category_id,is_trashed=False).first()
    category.is_trashed = True
    category.trashed_at = timezone.now()
    category.save(update_fields=["is_trashed","trashed_at"])
    messages.success(request,f'"{category.name}" deleted successfully.')
    return redirect("customadmin:category_management")

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from .forms import ProductForm, ProductVariantForm
from products.models import (
    Product,
    ProductImage,
    ProductVariant,
    ProductVariantImage,
)


@never_cache
@login_required
def add_product(request):

    if not request.user.is_superuser:
        return redirect("users:home")

    if request.method == "POST":

        form = ProductForm(request.POST)
        custom_errors = []

        allowed_types = [
            "image/jpeg",
            "image/png",
            "image/webp",
        ]

        max_image_size = 5 * 1024 * 1024  # 5 MB

        product_image_fields = {
            "main": "product_image_main",
            "front": "product_image_front",
            "side": "product_image_side",
            "back": "product_image_back",
        }

        product_images = []

        for image_type, field_name in product_image_fields.items():

            image = request.FILES.get(field_name)

            if image:

                product_images.append({
                    "image_type": image_type,
                    "image": image,
                })

                if image.size > max_image_size:
                    custom_errors.append(
                        f"{image.name} is larger than 5 MB."
                    )

                if image.content_type not in allowed_types:
                    custom_errors.append(
                        f"{image.name}: only JPG, PNG and WEBP images are allowed."
                    )

        if not request.FILES.get("product_image_main"):
            custom_errors.append(
                "Main product image is required."
            )

        if len(product_images) < 3:
            custom_errors.append(
                "Please upload at least 3 product images."
            )

        variant_indexes = request.POST.getlist(
            "variant_index"
        )

        variant_indexes = [
            index.strip()
            for index in variant_indexes
            if index.strip()
        ]

        validated_variants = []

        for position, index in enumerate(
            variant_indexes,
            start=1
        ):

            sale_price = request.POST.get(
                f"variant_sale_price_{index}",
                ""
            ).strip()

            discount_price = request.POST.get(
                f"variant_discount_price_{index}",
                ""
            ).strip()

            color = request.POST.get(
                f"variant_color_{index}",
                ""
            ).strip()

            size = request.POST.get(
                f"variant_size_{index}",
                ""
            ).strip()

            product_code = request.POST.get(
                f"variant_product_code_{index}",
                ""
            ).strip()

            quantity = request.POST.get(
                f"variant_quantity_{index}",
                "0"
            ).strip()

            is_active = bool(
                request.POST.get(
                    f"variant_is_active_{index}"
                )
            )

            variant_image_fields = {
                "main": f"variant_image_main_{index}",
                "front": f"variant_image_front_{index}",
                "side": f"variant_image_side_{index}",
                "back": f"variant_image_back_{index}",
            }

            variant_images = []

            for image_type, field_name in variant_image_fields.items():

                image = request.FILES.get(field_name)

                if image:

                    variant_images.append({
                        "image_type": image_type,
                        "image": image,
                    })

                    if image.size > max_image_size:
                        custom_errors.append(
                            f"Variant {position}: "
                            f"{image.name} is larger than 5 MB."
                        )

                    if image.content_type not in allowed_types:
                        custom_errors.append(
                            f"Variant {position}: "
                            f"{image.name} must be JPG, PNG or WEBP."
                        )

            if len(variant_images) < 1:
                custom_errors.append(
                    f"Variant {position} must have at least one image."
                )

            variant_data = {
                "sale_price": sale_price,
                "discount_price": discount_price,
                "color": color,
                "size": size,
                "product_code": product_code,
                "quantity": quantity,
                "is_active": is_active,
            }

            variant_form = ProductVariantForm(
                variant_data
            )

            if not variant_form.is_valid():

                for field, errors in variant_form.errors.items():

                    for error in errors:

                        if field == "__all__":

                            custom_errors.append(
                                f"Variant {position}: {error}"
                            )

                        else:

                            custom_errors.append(
                                f"Variant {position} - "
                                f"{field}: {error}"
                            )

            validated_variants.append({
                "index": index,
                "form": variant_form,
                "images": variant_images,
            })

        for error in custom_errors:

            form.add_error(
                None,
                error
            )

       
        if not form.is_valid() or custom_errors:

            return render(
                request,
                "add_product.html",
                {
                    "form": form,
                }
            )

       

        try:

            with transaction.atomic():

                product = form.save()


                for position, image_data in enumerate(
                    product_images
                ):

                    ProductImage.objects.create(
                        product=product,
                        image=image_data["image"],
                        image_type=image_data["image_type"],
                        position=position,
                    )


                for variant_data in validated_variants:

                    variant_form = variant_data["form"]

                    variant = ProductVariant.objects.create(
                        product=product,

                        sale_price=variant_form.cleaned_data[
                            "sale_price"
                        ],

                        discount_price=variant_form.cleaned_data.get(
                            "discount_price"
                        ),

                        color=variant_form.cleaned_data.get(
                            "color"
                        ),

                        size=variant_form.cleaned_data.get(
                            "size"
                        ),

                        product_code=variant_form.cleaned_data.get(
                            "product_code"
                        ),

                        quantity=variant_form.cleaned_data.get(
                            "quantity",
                            0
                        ),

                        is_active=variant_form.cleaned_data.get(
                            "is_active",
                            True
                        ),
                    )

                

                    for image_position, image_data in enumerate(
                        variant_data["images"]
                    ):

                        ProductVariantImage.objects.create(
                            variant=variant,

                            image=image_data["image"],

                            image_type=image_data["image_type"],

                            position=image_position,
                        )

            messages.success(
                request,
                "Product added successfully."
            )

            return redirect(
                "customadmin:list_product"
            )

        except Exception as error:

            form.add_error(
                None,
                f"Unable to add product: {error}"
            )

            return render(
                request,
                "add_product.html",
                {
                    "form": form,
                }
            )

    form = ProductForm()

    return render(
        request,
        "add_product.html",
        {
            "form": form,
        }
    )

@never_cache
@login_required
def list_product(request):

    search = request.GET.get(
        "search",
        ""
    ).strip()

    product_list = (
        Product.objects
        .filter(
            is_deleted=False
        )
        .select_related(
            "category",
            "main_image"
        )
        .order_by(
            "id"
        )
    )

    if search:
        product_list = product_list.filter(
            Q(name__icontains=search) |
            Q(category__name__icontains=search)
        )

    paginator = Paginator(
        product_list,
        6
    )

    page_number = request.GET.get(
        "page"
    )

    products = paginator.get_page(
        page_number
    )

    return render(
        request,
        "list_product.html",
        {
            "products": products,
            "search": search,
        }
    )

@never_cache
@login_required
def view_product(request):

    if not request.user.is_superuser:
        return redirect("users:home")

    if request.method != "POST":

        return HttpResponseNotAllowed(
            ["POST"]
        )

    product_id = request.POST.get(
        "product_id"
    )

    if not product_id:

        return render(
            request,
            "view_product.html",
            {
                "product": None,
                "error_message": "Product ID is missing."
            }
        )

    product = (
        Product.objects
        .filter(id=product_id)
        .select_related(
            "category",
            "main_image"
        )
        .prefetch_related(
            "images",
            "variants__images"
        )
        .first()
    )

    if product is None:

        return render(
            request,
            "view_product.html",
            {
                "product": None,
                "error_message": "Product not found."
            }
        )

    variants = product.variants.all()

    total_variant_stock = sum(
        variant.quantity or 0
        for variant in variants
    )

    context = {
        "product": product,
        "product_images": product.images.all(),
        "variants": variants,
        "total_variant_stock": total_variant_stock,
    }

    return render(
        request,
        "view_product.html",
        context
    )

@never_cache
@login_required
def edit_product(request):

    
    if not request.user.is_superuser:
        return redirect("users:home")

    product_id = request.POST.get("product_id")

    if not product_id:
        messages.error(
            request,
            "Product ID is required."
        )

        return redirect(
            "customadmin:list_product"
        )

    product = (
        Product.objects
        .filter(
            id=product_id,
            is_deleted=False
        )
        .select_related(
            "category",
            "main_image"
        )
        .prefetch_related(
            "images",
            "variants__images"
        )
        .first()
    )

    if product is None:

        messages.error(
            request,
            "Product not found."
        )

        return redirect(
            "customadmin:list_product"
        )

    action = request.POST.get("action")

    if action == "edit":

        form = ProductForm(
            instance=product
        )

        return render(
            request,
            "edit_product.html",
            {
                "form": form,
                "product": product,
                "variants": product.variants.all(),
                "product_images": product.images.all(),
            }
        )

    if action != "update":

        messages.error(
            request,
            "Invalid product request."
        )

        return redirect(
            "customadmin:list_product"
        )

    form = ProductForm(
        request.POST,
        instance=product
    )

    product_valid = form.is_valid()

    custom_errors = []
    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    image_types = [
        "main",
        "front",
        "side",
        "back",
    ]

    

    new_product_images = request.FILES.getlist(
        "product_images"
    )

    existing_product_image_types = set(
        product.images.values_list(
            "image_type",
            flat=True
        )
    )

    available_product_image_types = [
        image_type
        for image_type in image_types
        if image_type not in existing_product_image_types
    ]

    if len(new_product_images) > len(
        available_product_image_types
    ):

        custom_errors.append(
            "Only "
            f"{len(available_product_image_types)} "
            "additional product image(s) can be added. "
            "A product can have only Main, Front, Side and Back images."
        )

    for image in new_product_images:

        if image.size > 5 * 1024 * 1024:

            custom_errors.append(
                f"{image.name} is larger than 5 MB."
            )

        if image.content_type not in allowed_types:

            custom_errors.append(
                f"{image.name}: only JPG, PNG and WEBP "
                "images are allowed."
            )

    variant_indexes = request.POST.getlist(
        "variant_index"
    )

    variant_indexes = [
        index.strip()
        for index in variant_indexes
        if index.strip()
    ]



    if len(variant_indexes) < 2:

        custom_errors.append(
            "Please keep at least 2 product variants."
        )

    # =========================================================
    # GET CURRENT VARIANTS
    # =========================================================

    current_variants = {
        str(variant.id): variant
        for variant in product.variants.all()
    }

    submitted_existing_variant_ids = set()

    validated_variants = []

    submitted_product_codes = set()

    # =========================================================
    # PROCESS VARIANTS
    # =========================================================

    for position, index in enumerate(
        variant_indexes,
        start=1
    ):

        # -----------------------------------------------------
        # EXISTING VARIANT ID
        # -----------------------------------------------------

        variant_id = request.POST.get(
            f"variant_id_{index}",
            ""
        ).strip()

        existing_variant = None

        if variant_id:

            existing_variant = current_variants.get(
                variant_id
            )

            if existing_variant is None:

                custom_errors.append(
                    f"Variant {position}: invalid variant."
                )

            else:

                submitted_existing_variant_ids.add(
                    existing_variant.id
                )

        # -----------------------------------------------------
        # FIELD VALUES
        # -----------------------------------------------------

        sale_price = request.POST.get(
            f"variant_sale_price_{index}",
            ""
        ).strip()

        discount_price = request.POST.get(
            f"variant_discount_price_{index}",
            ""
        ).strip()

        color = request.POST.get(
            f"variant_color_{index}",
            ""
        ).strip()

        size = request.POST.get(
            f"variant_size_{index}",
            ""
        ).strip()

        product_code = request.POST.get(
            f"variant_product_code_{index}",
            ""
        ).strip()

        quantity = request.POST.get(
            f"variant_quantity_{index}",
            ""
        ).strip()

        # -----------------------------------------------------
        # ACTIVE
        # -----------------------------------------------------

        active_field = (
            f"variant_is_active_{index}"
        )

        active_value = request.POST.get(
            active_field
        )

        is_active = (
            active_value in [
                "1",
                "true",
                "True",
                "on",
            ]
        )

        # -----------------------------------------------------
        # VARIANT IMAGES
        # -----------------------------------------------------

        variant_images = request.FILES.getlist(
            f"variant_images_{index}"
        )

        # Existing variant backward-compatible field
        if (
            not variant_images
            and index.startswith("existing_")
        ):

            existing_id = index[
                len("existing_"):
            ]

            variant_images = request.FILES.getlist(
                f"variant_images_existing_{existing_id}"
            )

        # -----------------------------------------------------
        # VARIANT FORM DATA
        # -----------------------------------------------------

        variant_data = {
            "sale_price": sale_price,
            "discount_price": discount_price,
            "color": color,
            "size": size,
            "product_code": product_code,
            "quantity": quantity,
            "is_active": is_active,
        }

        # -----------------------------------------------------
        # FORM
        # -----------------------------------------------------

        if existing_variant:

            variant_form = ProductVariantForm(
                data=variant_data,
                instance=existing_variant
            )

        else:

            variant_form = ProductVariantForm(
                data=variant_data
            )

        variant_valid = variant_form.is_valid()

        # -----------------------------------------------------
        # VARIANT FORM ERRORS
        # -----------------------------------------------------

        if not variant_valid:

            field_labels = {
                "sale_price": "Sale price",
                "discount_price": "Discount price",
                "color": "Color",
                "size": "Size",
                "product_code": "Product code",
                "quantity": "Quantity",
                "is_active": "Active status",
                "__all__": "Variant",
            }

            for field, errors in variant_form.errors.items():

                field_label = field_labels.get(
                    field,
                    field.replace(
                        "_",
                        " "
                    ).title()
                )

                for error in errors:

                    custom_errors.append(
                        f"Variant {position}: "
                        f"{field_label} - {error}"
                    )

        # -----------------------------------------------------
        # DUPLICATE PRODUCT CODE IN CURRENT SUBMISSION
        # -----------------------------------------------------

        if product_code:

            normalized_code = product_code.strip().upper()

            if normalized_code in submitted_product_codes:

                custom_errors.append(
                    f"Variant {position}: "
                    "This product code is duplicated "
                    "in the submitted variants."
                )

            else:

                submitted_product_codes.add(
                    normalized_code
                )

        # -----------------------------------------------------
        # VARIANT IMAGE TYPES
        # -----------------------------------------------------

        if existing_variant:

            existing_variant_image_types = set(
                existing_variant.images.values_list(
                    "image_type",
                    flat=True
                )
            )

        else:

            existing_variant_image_types = set()

        available_variant_image_types = [
            image_type
            for image_type in image_types
            if image_type not in existing_variant_image_types
        ]

        # -----------------------------------------------------
        # IMAGE COUNT
        # -----------------------------------------------------

        if len(variant_images) > len(
            available_variant_image_types
        ):

            custom_errors.append(
                f"Variant {position}: "
                f"Only {len(available_variant_image_types)} "
                "additional image(s) can be added. "
                "Maximum is Main, Front, Side and Back."
            )

        # -----------------------------------------------------
        # IMAGE VALIDATION
        # -----------------------------------------------------

        for image in variant_images:

            if image.size > 5 * 1024 * 1024:

                custom_errors.append(
                    f"Variant {position}: "
                    f"{image.name} is larger than 5 MB."
                )

            if image.content_type not in allowed_types:

                custom_errors.append(
                    f"Variant {position}: "
                    f"{image.name} must be JPG, PNG or WEBP."
                )

        # -----------------------------------------------------
        # STORE
        # -----------------------------------------------------

        validated_variants.append(
            {
                "index": index,
                "variant_id": variant_id,
                "existing_variant": existing_variant,
                "form": variant_form,
                "valid": variant_valid,
                "images": variant_images,
            }
        )

    # =========================================================
    # CHECK PRODUCT FORM ERRORS
    # =========================================================

    if not product_valid:

        for field, errors in form.errors.items():

            field_label = field.replace(
                "_",
                " "
            ).title()

            for error in errors:

                if field == "__all__":

                    custom_errors.append(
                        str(error)
                    )

                else:

                    custom_errors.append(
                        f"Product {field_label}: {error}"
                    )

    # =========================================================
    # CROSS-CHECK VARIANT PRODUCT CODES
    # =========================================================

    for item in validated_variants:

        variant_form = item["form"]

        if not variant_form.is_valid():
            continue

        code = (
            variant_form.cleaned_data
            .get("product_code")
        )

        if not code:
            continue

        code = code.strip().upper()

        # -----------------------------------------------------
        # OTHER VARIANTS
        # -----------------------------------------------------

        existing_variants_query = (
            ProductVariant.objects
            .filter(
                product_code__iexact=code
            )
        )

        if item["existing_variant"]:

            existing_variants_query = (
                existing_variants_query
                .exclude(
                    pk=item["existing_variant"].pk
                )
            )

        if existing_variants_query.exists():

            custom_errors.append(
                f"Variant {item['index']}: "
                "This product code is already used "
                "by another variant."
            )

        # -----------------------------------------------------
        # BASE PRODUCT
        # -----------------------------------------------------

        product_query = Product.objects.filter(
            product_code__iexact=code
        )

        if product_query.exists():

            custom_errors.append(
                f"Variant {item['index']}: "
                "This product code is already used "
                "by a base product."
            )

    # =========================================================
    # CHECK BASE PRODUCT CODE AGAINST VARIANTS
    # =========================================================

    if product_valid:

        base_product_code = (
            form.cleaned_data.get(
                "product_code"
            )
        )

        if base_product_code:

            base_product_code = (
                base_product_code
                .strip()
                .upper()
            )

            variant_query = (
                ProductVariant.objects
                .filter(
                    product_code__iexact=base_product_code
                )
            )

            if variant_query.exists():

                custom_errors.append(
                    "Product code is already used "
                    "by a product variant."
                )

    # =========================================================
    # VALIDATION FAILED
    # =========================================================

    if custom_errors:

        # Remove duplicate error messages
        unique_errors = list(
            dict.fromkeys(
                custom_errors
            )
        )

        for error in unique_errors:

            form.add_error(
                None,
                error
            )

        return render(
            request,
            "edit_product.html",
            {
                "form": form,
                "product": product,
                "variants": product.variants.all(),
                "product_images": product.images.all(),
            }
        )

    
    try:

        with transaction.atomic():


            product = form.save()

            # =================================================
            # PRODUCT IMAGES
            # =================================================

            current_product_types = set(
                product.images.values_list(
                    "image_type",
                    flat=True
                )
            )

            available_product_types = [
                image_type
                for image_type in image_types
                if image_type not in current_product_types
            ]

            current_position = (
                product.images.count()
            )

            for image_type, image in zip(
                available_product_types,
                new_product_images
            ):

                ProductImage.objects.create(
                    product=product,
                    image_type=image_type,
                    image=image,
                    position=current_position
                )

                current_position += 1

            # =================================================
            # SAVE VARIANTS
            # =================================================

            saved_variant_ids = []

            for item in validated_variants:

                variant_form = item["form"]

                existing_variant = (
                    item["existing_variant"]
                )

                # =============================================
                # UPDATE EXISTING
                # =============================================

                if existing_variant:

                    variant = existing_variant

                    variant.sale_price = (
                        variant_form.cleaned_data[
                            "sale_price"
                        ]
                    )

                    variant.discount_price = (
                        variant_form.cleaned_data[
                            "discount_price"
                        ]
                    )

                    variant.color = (
                        variant_form.cleaned_data[
                            "color"
                        ]
                    )

                    variant.size = (
                        variant_form.cleaned_data[
                            "size"
                        ]
                    )

                    variant.product_code = (
                        variant_form.cleaned_data[
                            "product_code"
                        ]
                    )

                    variant.quantity = (
                        variant_form.cleaned_data[
                            "quantity"
                        ]
                    )

                    variant.is_active = (
                        variant_form.cleaned_data[
                            "is_active"
                        ]
                    )

                    variant.save()

                # =============================================
                # CREATE NEW
                # =============================================

                else:

                    variant = (
                        ProductVariant.objects.create(
                            product=product,
                            sale_price=(
                                variant_form.cleaned_data[
                                    "sale_price"
                                ]
                            ),
                            discount_price=(
                                variant_form.cleaned_data[
                                    "discount_price"
                                ]
                            ),
                            color=(
                                variant_form.cleaned_data[
                                    "color"
                                ]
                            ),
                            size=(
                                variant_form.cleaned_data[
                                    "size"
                                ]
                            ),
                            product_code=(
                                variant_form.cleaned_data[
                                    "product_code"
                                ]
                            ),
                            quantity=(
                                variant_form.cleaned_data[
                                    "quantity"
                                ]
                            ),
                            is_active=(
                                variant_form.cleaned_data[
                                    "is_active"
                                ]
                            ),
                        )
                    )

                saved_variant_ids.append(
                    variant.id
                )

                # =============================================
                # VARIANT IMAGES
                # =============================================

                variant_images = item["images"]

                if variant_images:

                    existing_types = set(
                        variant.images.values_list(
                            "image_type",
                            flat=True
                        )
                    )

                    available_types = [
                        image_type
                        for image_type in image_types
                        if image_type not in existing_types
                    ]

                    position = (
                        variant.images.count()
                    )

                    for image_type, image in zip(
                        available_types,
                        variant_images
                    ):

                        ProductVariantImage.objects.create(
                            variant=variant,
                            image_type=image_type,
                            image=image,
                            position=position
                        )

                        position += 1

            # =================================================
            # DELETE REMOVED VARIANTS
            # =================================================

            product.variants.exclude(
                id__in=saved_variant_ids
            ).delete()

            # =================================================
            # SET MAIN IMAGE
            # =================================================

            main_image = (
                product.images
                .filter(
                    image_type="main"
                )
                .first()
            )

            if main_image:

                if product.main_image_id != main_image.id:

                    product.main_image = main_image

                    product.save(
                        update_fields=[
                            "main_image"
                        ]
                    )

            elif product.images.exists():

                first_image = (
                    product.images
                    .order_by(
                        "position",
                        "id"
                    )
                    .first()
                )

                product.main_image = first_image

                product.save(
                    update_fields=[
                        "main_image"
                    ]
                )

            else:

                # No images remain
                product.main_image = None

                product.save(
                    update_fields=[
                        "main_image"
                    ]
                )

        # =====================================================
        # SUCCESS
        # =====================================================

        messages.success(
            request,
            "Product updated successfully."
        )

        return redirect(
            "customadmin:list_product"
        )

    # =========================================================
    # DATABASE / UNEXPECTED ERROR
    # =========================================================

    except Exception as error:

        messages.error(
            request,
            f"Unable to update product: {error}"
        )

        form.add_error(
            None,
            f"Unable to update product: {error}"
        )

        return render(
            request,
            "edit_product.html",
            {
                "form": form,
                "product": product,
                "variants": product.variants.all(),
                "product_images": product.images.all(),
            }
        )
    
@never_cache
@login_required
def delete_product_image(request):

    if not request.user.is_superuser:
        return JsonResponse(
            {
                "success": False,
                "message": "Permission denied."
            },
            status=403
        )

    if request.method != "POST":

        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request."
            },
            status=400
        )

    image_id = request.POST.get(
        "image_id"
    )

    if not image_id:

        return JsonResponse(
            {
                "success": False,
                "message": "Image ID is required."
            },
            status=400
        )

    image = (
        ProductImage.objects
        .select_related("product")
        .filter(id=image_id)
        .first()
    )

    if image is None:

        return JsonResponse(
            {
                "success": False,
                "message": "Product image not found."
            },
            status=404
        )

    try:

        product = image.product

        was_main_image = (
            product.main_image_id == image.id
        )

        image.delete()


        if was_main_image:

            next_image = (
                product.images
                .order_by(
                    "position",
                    "id"
                )
                .first()
            )

            product.main_image = next_image

            product.save(
                update_fields=["main_image"]
            )

        return JsonResponse(
            {
                "success": True,
                "message": "Product image deleted successfully.",
                "product_id": product.id,
            }
        )

    except Exception as error:

        return JsonResponse(
            {
                "success": False,
                "message": f"Unable to delete image: {error}"
            },
            status=500
        )
    
@never_cache
@login_required
def delete_variant_image(request):

    if not request.user.is_superuser:
        return JsonResponse(
            {
                "success": False,
                "message": "Permission denied."
            },
            status=403
        )

    if request.method != "POST":

        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request."
            },
            status=400
        )

    image_id = request.POST.get(
        "image_id"
    )

    if not image_id:

        return JsonResponse(
            {
                "success": False,
                "message": "Image ID is required."
            },
            status=400
        )

    image = (
        ProductVariantImage.objects
        .select_related(
            "variant",
            "variant__product"
        )
        .filter(id=image_id)
        .first()
    )

    if image is None:

        return JsonResponse(
            {
                "success": False,
                "message": "Variant image not found."
            },
            status=404
        )

    try:

        variant = image.variant
        product = variant.product

        image.delete()

        return JsonResponse(
            {
                "success": True,
                "message": "Variant image deleted successfully.",
                "variant_id": variant.id,
                "product_id": product.id,
            }
        )

    except Exception as error:

        return JsonResponse(
            {
                "success": False,
                "message": f"Unable to delete variant image: {error}"
            },
            status=500
        )

@never_cache
@login_required
def delete_product(request):

    if not request.user.is_superuser:

        return JsonResponse(
            {
                "success": False,
                "message": "You do not have permission to delete products."
            },
            status=403
        )

    if request.method != "POST":

        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request method."
            },
            status=400
        )

    product_id = request.POST.get(
        "product_id"
    )

    if not product_id:

        return JsonResponse(
            {
                "success": False,
                "message": "Product ID is required."
            },
            status=400
        )

    try:

        product = (
            Product.objects
            .filter(
                id=product_id,
                is_deleted=False
            )
            .first()
        )

        if product is None:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Product not found or already deleted."
                },
                status=404
            )

        product.is_deleted = True
        product.is_active = False

        product.save(
            update_fields=[
                "is_deleted",
                "is_active"
            ]
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Product deleted successfully.",
                "product_id": product.id
            }
        )

    except Exception:

        return JsonResponse(
            {
                "success": False,
                "message": "An unexpected error occurred while deleting the product."
            },
            status=500
        )
        
@never_cache
@login_required
def order_management(request):

    if not request.user.is_superuser:
        return redirect("users:home")

    search = request.GET.get(
        "search",
        ""
    ).strip()

    status = request.GET.get(
        "status",
        ""
    ).strip()

    sort = request.GET.get(
        "sort",
        "newest"
    ).strip()

    orders = (
        Order.objects
        .select_related(
            "user",
            "address"
        )
        .prefetch_related(
            "items"
        )
    )

    if search:

        search_filter = (
            Q(id__icontains=search)
            |
            Q(user__username__icontains=search)
            |
            Q(user__first_name__icontains=search)
            |
            Q(user__last_name__icontains=search)
            |
            Q(user__email__icontains=search)
        )

        orders = orders.filter(
            search_filter
        )

   
    if status:

        orders = orders.filter(
            status=status
        )

    if sort == "oldest":

        orders = orders.order_by(
            "created_at"
        )

    elif sort == "amount_low":

        orders = orders.order_by(
            "total_amount",
            "-created_at"
        )

    elif sort == "amount_high":

        orders = orders.order_by(
            "-total_amount",
            "-created_at"
        )

    else:

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

    orders_page = paginator.get_page(
        page_number
    )

    context = {

        "orders": orders_page,

        "search": search,

        "selected_status": status,

        "selected_sort": sort,

        "status_choices": Order.STATUS_CHOICES,

    }

    return render(
        request,
        "order_management.html",
        context
    )

@never_cache
@login_required
def admin_order_detail(request):

    if not request.user.is_superuser:
        return redirect("users:home")

    if request.method != "POST":

        messages.error(
            request,
            "Invalid request."
        )

        return redirect(
            "customadmin:order_management"
        )

    order_id = request.POST.get("order_id")

    if not order_id:

        messages.error(
            request,
            "Order ID is required."
        )

        return redirect(
            "customadmin:order_management"
        )

    order = (
        Order.objects
        .filter(
            id=order_id
        )
        .select_related(
            "user",
            "address",
        )
        .prefetch_related(
            "items__product",
            "items__product__images",
            "items__variant",
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
            "customadmin:order_management"
        )

    # -------------------------------------------------
    # Prepare product / variant image information
    # -------------------------------------------------

    for item in order.items.all():

        # ---------------------------------------------
        # VARIANT ORDER ITEM
        # ---------------------------------------------

        if item.variant_id:

            variant_images = list(
                item.variant.images.all()
            )

            # Variant main image
            main_variant_image = next(
                (
                    image
                    for image in variant_images
                    if image.image_type == "main"
                ),
                None
            )

            if main_variant_image:

                item.display_image = main_variant_image

            elif variant_images:

                # If no main image, use first variant image
                item.display_image = variant_images[0]

            else:

                # Fallback to base product image
                product_images = list(
                    item.product.images.all()
                )

                if item.product.main_image:

                    item.display_image = (
                        item.product.main_image
                    )

                elif product_images:

                    item.display_image = (
                        product_images[0]
                    )

                else:

                    item.display_image = None

        # ---------------------------------------------
        # BASE PRODUCT ORDER ITEM
        # ---------------------------------------------

        else:

            product_images = list(
                item.product.images.all()
            )

            if item.product.main_image:

                item.display_image = (
                    item.product.main_image
                )

            elif product_images:

                item.display_image = (
                    product_images[0]
                )

            else:

                item.display_image = None

    return render(
        request,
        "admin_order_detail.html",
        {
            "order": order,
        }
    )

@never_cache
@login_required
@transaction.atomic
def update_order_status(request):

    if not request.user.is_superuser:
        return redirect("users:home")

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    order_id = request.POST.get("order_id")
    new_status = request.POST.get("status")

    if not order_id:

        messages.error(
            request,
            "Order ID is required."
        )

        return redirect(
            "customadmin:order_management"
        )

    valid_statuses = dict(
        Order.STATUS_CHOICES
    )

    if new_status not in valid_statuses:

        messages.error(
            request,
            "Invalid order status."
        )

        return redirect(
            "customadmin:order_management"
        )

    order = (
        Order.objects
        .select_for_update()
        .filter(
            id=order_id
        )
        .prefetch_related(
            "items__product",
            "items__variant"
        )
        .first()
    )

    if not order:

        messages.error(
            request,
            "Order not found."
        )

        return redirect(
            "customadmin:order_management"
        )

    old_status = order.status

    if old_status == new_status:

        messages.info(
            request,
            f"Order #{order.id} is already {new_status}."
        )

        return redirect(
            "customadmin:order_management"
        )

    if old_status == "Cancelled":

        messages.error(
            request,
            "A cancelled order cannot be reopened."
        )

        return redirect(
            "customadmin:order_management"
        )

    if old_status == "Delivered":

        messages.error(
            request,
            "A delivered order cannot be changed."
        )

        return redirect(
            "customadmin:order_management"
        )

    if new_status == "Cancelled":

        restocked_count = 0

        for item in order.items.all():

            if item.is_cancelled:
                continue

            if item.is_returned:
                continue

            # Variant-based inventory restoration
            if item.variant:

                item.variant.quantity += item.quantity

                item.variant.save(
                    update_fields=[
                        "quantity"
                    ]
                )

                restocked_count += item.quantity

            item.is_cancelled = True

            item.cancellation_reason = (
                "Cancelled by admin."
            )

            item.save(
                update_fields=[
                    "is_cancelled",
                    "cancellation_reason"
                ]
            )

        order.status = "Cancelled"

        order.save(
            update_fields=[
                "status",
                "updated_at"
            ]
        )

        messages.success(
            request,
            "Order cancelled successfully. "
            f"{restocked_count} item(s) returned to inventory."
        )

        return redirect(
            "customadmin:order_management"
        )

    order.status = new_status

    order.save(
        update_fields=[
            "status",
            "updated_at"
        ]
    )

    messages.success(
        request,
        f"Order #{order.id} status changed "
        f"from {old_status} to {new_status}."
    )

    return redirect(
        "customadmin:order_management"
    )

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import (
    Q,
    Sum,
    Prefetch,
    Case,
    When,
    Value,
    BooleanField,
)
from django.db.models.functions import Coalesce
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from products.models import Product, ProductVariant


@never_cache
@login_required
def inventory_management(request):

    if not request.user.is_superuser:
        return redirect("users:home")

    search = request.GET.get("search", "").strip()
    stock_filter = request.GET.get("stock", "").strip()
    selected_sort = request.GET.get("sort", "name").strip()


    # ==========================================================
    # BASE PRODUCTS
    # ==========================================================

    inventory_products = Product.objects.filter(
        is_deleted=False,
        is_active=True,
    )


    # ==========================================================
    # BASE PRODUCT STOCK
    # ==========================================================

    base_stock_total = (
        inventory_products.aggregate(
            total=Coalesce(
                Sum("quantity"),
                Value(0)
            )
        )["total"]
    )

    base_low_stock = inventory_products.filter(
        quantity__gt=0,
        quantity__lte=5,
    ).count()

    base_out_of_stock = inventory_products.filter(
        quantity=0,
    ).count()


    # ==========================================================
    # VARIANT STOCK
    # ==========================================================

    inventory_variants = ProductVariant.objects.filter(
        product__is_deleted=False,
        product__is_active=True,
        is_active=True,
    )

    variant_stock_total = (
        inventory_variants.aggregate(
            total=Coalesce(
                Sum("quantity"),
                Value(0)
            )
        )["total"]
    )

    variant_low_stock = inventory_variants.filter(
        quantity__gt=0,
        quantity__lte=5,
    ).count()

    variant_out_of_stock = inventory_variants.filter(
        quantity=0,
    ).count()


    # ==========================================================
    # SUMMARY
    # ==========================================================

    total_products = inventory_products.count()

    available_stock = (
        base_stock_total +
        variant_stock_total
    )

    low_stock = (
        base_low_stock +
        variant_low_stock
    )

    out_of_stock = (
        base_out_of_stock +
        variant_out_of_stock
    )


    # ==========================================================
    # PRODUCT QUERY
    # ==========================================================

    products = (
        Product.objects
        .filter(
            is_deleted=False,
            is_active=True,
        )
        .select_related(
            "category",
            "main_image",
        )
    )


    # ==========================================================
    # SEARCH CONDITIONS
    # ==========================================================

    base_search = Q()

    variant_search = Q()

    if search:

        base_search = (
            Q(name__icontains=search)
            | Q(category__name__icontains=search)
            | Q(product_code__icontains=search)
            | Q(color__icontains=search)
            | Q(size__icontains=search)
        )

        variant_search = (
            Q(variants__product_code__icontains=search)
            | Q(variants__color__icontains=search)
            | Q(variants__size__icontains=search)
        )


  

    base_stock_condition = Q()

    variant_stock_condition = Q(
        variants__is_active=True
    )


    if stock_filter == "available":

        base_stock_condition = Q(
            quantity__gt=5
        )

        variant_stock_condition = Q(
            variants__is_active=True,
            variants__quantity__gt=5,
        )


    elif stock_filter == "low":

        base_stock_condition = Q(
            quantity__gt=0,
            quantity__lte=5,
        )

        variant_stock_condition = Q(
            variants__is_active=True,
            variants__quantity__gt=0,
            variants__quantity__lte=5,
        )


    elif stock_filter == "out":

        base_stock_condition = Q(
            quantity=0
        )

        variant_stock_condition = Q(
            variants__is_active=True,
            variants__quantity=0,
        )


    # ==========================================================
    # DETERMINE WHICH INVENTORY ROWS SHOULD BE DISPLAYED
    # ==========================================================

    has_filter = bool(search or stock_filter)


    if has_filter:

        # Base product must match BOTH search and stock filter
        base_match = base_search & base_stock_condition

        # Variant must match BOTH search and stock filter
        variant_match = variant_search & Q(
            variants__is_active=True
        )

        if stock_filter == "available":

            variant_match &= Q(
                variants__quantity__gt=5
            )

        elif stock_filter == "low":

            variant_match &= Q(
                variants__quantity__gt=0,
                variants__quantity__lte=5,
            )

        elif stock_filter == "out":

            variant_match &= Q(
                variants__quantity=0
            )


    
        products = products.filter(
            base_match | variant_match
        ).distinct()


        products = products.annotate(
            show_base_inventory=Case(
                When(
                    base_match,
                    then=Value(True)
                ),
                default=Value(False),
                output_field=BooleanField(),
            )
        )

    else:

        products = products.annotate(
            show_base_inventory=Value(
                True,
                output_field=BooleanField()
            )
        )

    variant_queryset = (
        ProductVariant.objects
        .filter(
            is_active=True,
            product__is_deleted=False,
            product__is_active=True,
        )
        .prefetch_related("images")
    )
    
    if search:

        variant_queryset = variant_queryset.filter(
            Q(product_code__icontains=search)
            | Q(color__icontains=search)
            | Q(size__icontains=search)
        )

    if stock_filter == "available":

        variant_queryset = variant_queryset.filter(
            quantity__gt=5
        )

    elif stock_filter == "low":

        variant_queryset = variant_queryset.filter(
            quantity__gt=0,
            quantity__lte=5,
        )

    elif stock_filter == "out":

        variant_queryset = variant_queryset.filter(
            quantity=0
        )


    if selected_sort == "stock_low":

        products = products.order_by(
            "quantity",
            "name",
        )

        variant_queryset = variant_queryset.order_by(
            "quantity",
            "id",
        )


    elif selected_sort == "stock_high":

        products = products.order_by(
            "-quantity",
            "name",
        )

        variant_queryset = variant_queryset.order_by(
            "-quantity",
            "id",
        )


    elif selected_sort == "newest":

        products = products.order_by(
            "-created_at"
        )

        variant_queryset = variant_queryset.order_by(
            "id"
        )


    elif selected_sort == "updated":

        products = products.order_by(
            "-updated_at"
        )

        variant_queryset = variant_queryset.order_by(
            "id"
        )


    else:

        selected_sort = "name"

        products = products.order_by(
            "name"
        )

        variant_queryset = variant_queryset.order_by(
            "id"
        )

    products = products.prefetch_related(

        Prefetch(
            "variants",
            queryset=variant_queryset,
            to_attr="inventory_variants",
        ),

        "images",
    )
    filtered_product_count = products.count()

    paginator = Paginator(
        products,
        5
    )

    products_page = paginator.get_page(
        request.GET.get("page")
    )


    context = {

        "products": products_page,

        "products_page": products_page,

        "total_products": total_products,

        "base_stock_total": base_stock_total,
        "variant_stock_total": variant_stock_total,


        "available_stock": available_stock,

      
        "base_low_stock": base_low_stock,
        "variant_low_stock": variant_low_stock,
        "variant_stock_condition":variant_stock_condition,

        "base_out_of_stock": base_out_of_stock,
        "variant_out_of_stock": variant_out_of_stock,
        "low_stock": low_stock,
        "out_of_stock": out_of_stock,

        "filtered_product_count": filtered_product_count,

        "search": search,

        "stock_filter": stock_filter,

        "selected_sort": selected_sort,
    }

    return render(
        request,
        "inventory_management.html",
        context,
    )

@never_cache
@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("users:signin")