import re
from django import forms
from .models import Category
from products.models import Product, ProductVariant
from orders.models import Coupon
from decimal import Decimal

class CategoryForm(forms.ModelForm):

    name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter category name",
                "maxlength": "100",
                "autocomplete": "off",
            }
        )
    )

    class Meta:
        model = Category
        fields = ["name"]

    def clean_name(self):

        name = self.cleaned_data["name"].strip()

        if not name:
            raise forms.ValidationError(
                "Category name cannot be empty."
            )

        if not re.fullmatch(
            r"[A-Za-z ]+",
            name
        ):
            raise forms.ValidationError(
                "Category name can contain only letters and spaces."
            )

        if "  " in name:
            raise forms.ValidationError(
                "Category name cannot contain multiple consecutive spaces."
            )

        existing = Category.objects.filter(
            name__iexact=name,
            is_trashed=False
        )

        if self.instance and self.instance.pk:
            existing = existing.exclude(
                pk=self.instance.pk
            )

        if existing.exists():
            raise forms.ValidationError(
                "This category already exists."
            )

        return name

class ProductForm(forms.ModelForm):

    class Meta:

        model = Product

        fields = [
            "name",
            "category",
            "description",
            "sale_price",
            "discount_price",
            "color",
            "size",
            "product_code",
            "quantity",
            "is_active",
            "featured",
        ]

        widgets = {

            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Example: Rolex Submariner",
                    "maxlength": "200",
                    "autocomplete": "off",
                }
            ),

             "category": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter watch description",
                    "rows": 4,
                }
            ),

            "sale_price": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter sale price",
                    "min": "0.01",
                    "step": "0.01",
                }
            ),

            "discount_price": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter discounted price",
                    "min": "0.01",
                    "step": "0.01",
                }
            ),

            "color": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Example: Black",
                    "maxlength": "100",
                }
            ),

            "size": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Example: 42 mm",
                    "maxlength": "100",
                }
            ),

            "product_code": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Example: RLX-BLK-42",
                    "maxlength": "100",
                    "autocomplete": "off",
                }
            ),

            "quantity": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter stock quantity",
                    "min": "0",
                    "step": "1",
                }
            ),

            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),

            "featured": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
        }

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = (
            Category.objects
            .filter(
                is_trashed=False
            )
            .order_by("name")
        )

        self.fields["category"].empty_label = None
        self.fields["product_code"].required = True
        self.fields["color"].required = False
        self.fields["size"].required = False

    def clean_category(self):

        category = self.cleaned_data.get("category")

        if not category:
            raise forms.ValidationError(
                "Please select a category."
            )

        if category.is_trashed:
            raise forms.ValidationError(
                "This category is no longer available."
            )

        return category

    def clean_name(self):

        name = self.cleaned_data.get("name")

        if not name:
            raise forms.ValidationError(
                "Watch name is required."
            )

        name = name.strip()

        if not name:
            raise forms.ValidationError(
                "Watch name cannot contain only spaces."
            )

        if not re.fullmatch(
            r"[A-Za-z]+(?: [A-Za-z]+)*",
            name
        ):
            raise forms.ValidationError(
                "Watch name can contain only letters and single spaces between words."
            )

        return name

    def clean_description(self):

        description = self.cleaned_data.get("description")

        if not description:
            raise forms.ValidationError(
                "Watch description is required."
            )

        description = description.strip()

        if not description:
            raise forms.ValidationError(
                "Description cannot contain only spaces."
            )

        if re.search(
            r"\s{2,}",
            description
        ):
            raise forms.ValidationError(
                "Description cannot contain multiple consecutive spaces."
            )

        return description

    def clean_sale_price(self):

        sale_price = self.cleaned_data.get(
            "sale_price"
        )

        if sale_price is None:
            raise forms.ValidationError(
                "Sale price is required."
            )

        if sale_price <= 0:
            raise forms.ValidationError(
                "Sale price must be greater than zero."
            )

        return sale_price

    def clean_discount_price(self):

        discount_price = self.cleaned_data.get(
            "discount_price"
        )

        if discount_price is None:
            return None

        if discount_price <= 0:
            raise forms.ValidationError(
                "Discount price must be greater than zero."
            )

        return discount_price

    def clean_color(self):

        color = self.cleaned_data.get("color")

        if not color:
            return None

        color = color.strip()

        if not color:
            return None

        if not re.fullmatch(
            r"[A-Za-z]+(?: [A-Za-z]+)*",
            color
        ):
            raise forms.ValidationError(
                "Color can contain only letters and single spaces."
            )

        return color

    def clean_size(self):

        size = self.cleaned_data.get("size")

        if not size:
            return None

        size = size.strip()

        if not re.fullmatch(
            r"\d+(?: mm)?",
            size,
            re.IGNORECASE
        ):
            raise forms.ValidationError(
                "Size must be like 40, 42 or 42 mm."
            )

        return size

    def clean_product_code(self):

        product_code = self.cleaned_data.get(
            "product_code"
        )

        if not product_code:
            raise forms.ValidationError(
                "Product code is required."
            )

        product_code = product_code.strip().upper()

        if not re.fullmatch(
            r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*",
            product_code
        ):
            raise forms.ValidationError(
                "Product code can contain only letters, numbers and hyphens."
            )

        existing = Product.objects.filter(
            product_code__iexact=product_code
        )

        if self.instance and self.instance.pk:
            existing = existing.exclude(
                pk=self.instance.pk
            )

        if existing.exists():
            raise forms.ValidationError(
                "This product code already exists."
            )

        variant_existing = ProductVariant.objects.filter(
            product_code__iexact=product_code
        )

        if variant_existing.exists():
            raise forms.ValidationError(
                "This product code is already used by a product variant."
            )

        return product_code

    def clean_quantity(self):

        quantity = self.cleaned_data.get(
            "quantity"
        )

        if quantity is None:
            raise forms.ValidationError(
                "Product quantity is required."
            )

        if quantity < 0:
            raise forms.ValidationError(
                "Product quantity cannot be negative."
            )

        return quantity

    def clean(self):

        cleaned_data = super().clean()

        sale_price = cleaned_data.get(
            "sale_price"
        )

        discount_price = cleaned_data.get(
            "discount_price"
        )

        if (
            sale_price is not None
            and discount_price is not None
            and discount_price > sale_price
        ):
            self.add_error(
                "discount_price",
                "Discount price must be less than or equal to the sale price."
            )

        return cleaned_data
    
class ProductVariantForm(forms.ModelForm):

    class Meta:

        model = ProductVariant

        fields = [
            "sale_price",
            "discount_price",
            "color",
            "size",
            "product_code",
            "quantity",
            "is_active",
        ]

        widgets = {

            "sale_price": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter variant sale price",
                    "min": "0.01",
                    "step": "0.01",
                }
            ),

            "discount_price": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter variant discounted price",
                    "min": "0.01",
                    "step": "0.01",
                }
            ),

            "color": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Example: Black",
                    "maxlength": "100",
                }
            ),

            "size": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Example: 42 mm",
                    "maxlength": "100",
                }
            ),

            "product_code": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Example: RLX-BLK-42",
                    "maxlength": "100",
                    "autocomplete": "off",
                }
            ),

            "quantity": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter variant quantity",
                    "min": "0",
                    "step": "1",
                }
            ),

            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
        }

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.fields["sale_price"].required = True
        self.fields["discount_price"].required = False
        self.fields["color"].required = True
        self.fields["size"].required = True
        self.fields["product_code"].required = True
        self.fields["quantity"].required = True

    def clean_sale_price(self):

        sale_price = self.cleaned_data.get("sale_price")

        if sale_price is None:
            raise forms.ValidationError(
                "Variant sale price is required."
            )

        if sale_price <= 0:
            raise forms.ValidationError(
                "Variant sale price must be greater than zero."
            )

        return sale_price


    def clean_discount_price(self):

        discount_price = self.cleaned_data.get("discount_price")

        if discount_price in ("", None):
            return None

        if discount_price <= 0:
            raise forms.ValidationError(
                "Variant discount price must be greater than zero."
            )

        return discount_price


    def clean_color(self):

        color = self.cleaned_data.get("color")

        if not color:
            raise forms.ValidationError(
                "Color is required."
            )

        color = color.strip()

        if not color:
            raise forms.ValidationError(
                "Color is required."
            )

        if not re.fullmatch(
            r"[A-Za-z]+(?: [A-Za-z]+)*",
            color
        ):
            raise forms.ValidationError(
                "Color can contain only letters and single spaces."
            )

        return color


    def clean_size(self):

        size = self.cleaned_data.get("size")

        if not size:
            raise forms.ValidationError(
                "Watch size is required."
            )

        size = size.strip()

        if not re.fullmatch(
            r"\d+(?: mm)?",
            size,
            re.IGNORECASE
        ):
            raise forms.ValidationError(
                "Size must be like 40, 42 or 42 mm."
            )

        return size

    def clean_product_code(self):

        product_code = self.cleaned_data.get("product_code")

        if not product_code:
            raise forms.ValidationError(
                "Product code is required."
            )

        product_code = product_code.strip().upper()

        if not re.fullmatch(
            r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*",
            product_code
        ):
            raise forms.ValidationError(
                "Product code can contain only letters, numbers and hyphens."
            )

       
        existing_variant = ProductVariant.objects.filter(
            product_code__iexact=product_code
        )

        if self.instance and self.instance.pk:
            existing_variant = existing_variant.exclude(
                pk=self.instance.pk
            )

        if existing_variant.exists():
            raise forms.ValidationError(
                "This product code already exists for another variant."
            )

        existing_product = Product.objects.filter(
            product_code__iexact=product_code
        )

        if existing_product.exists():
            raise forms.ValidationError(
                "This product code is already used by a base product."
            )

        return product_code

    def clean_quantity(self):

        quantity = self.cleaned_data.get("quantity")

        if quantity is None:
            raise forms.ValidationError(
                "Variant quantity is required."
            )

        if quantity < 0:
            raise forms.ValidationError(
                "Variant quantity cannot be negative."
            )

        return quantity
        
    def clean(self):

        cleaned_data = super().clean()

        sale_price = cleaned_data.get("sale_price")
        discount_price = cleaned_data.get("discount_price")

        if (
            sale_price is not None
            and discount_price is not None
            and discount_price >= sale_price
        ):
            self.add_error(
                "discount_price",
                "Discount price must be less than the sale price."
            )

        return cleaned_data

class CouponForm(forms.ModelForm):

    class Meta:

        model = Coupon

        fields = [
            "code",
            "discount_type",
            "discount_value",
            "minimum_purchase",
            "maximum_discount",
            "start_date",
            "end_date",
            "usage_limit",
            "is_active",
        ]

        widgets = {

            "code": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Example: SAVE10",
                    "maxlength": "50",
                    "autocomplete": "off",
                }
            ),

            "discount_type": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "discount_value": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter discount",
                    "min": "0.01",
                    "step": "0.01",
                }
            ),

            "minimum_purchase": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Example: 1000",
                    "min": "0",
                    "step": "0.01",
                }
            ),

            "maximum_discount": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Optional maximum discount",
                    "min": "0.01",
                    "step": "0.01",
                }
            ),

            "start_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "end_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "usage_limit": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Example: 100",
                    "min": "1",
                    "step": "1",
                }
            ),

            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
        }

    def clean_code(self):

        code = self.cleaned_data.get("code")

        if not code:
            raise forms.ValidationError(
                "Coupon code is required."
            )

        code = code.strip().upper()

        if not code.replace("-", "").replace("_", "").isalnum():
            raise forms.ValidationError(
                "Coupon code can contain only letters, numbers, "
                "hyphens and underscores."
            )

        query = Coupon.objects.filter(
            code__iexact=code
        )

        if self.instance.pk:
            query = query.exclude(
                pk=self.instance.pk
            )

        if query.exists():
            raise forms.ValidationError(
                "A coupon with this code already exists."
            )

        return code

    def clean_discount_value(self):

        discount_type = self.cleaned_data.get(
            "discount_type"
        )

        discount_value = self.cleaned_data.get(
            "discount_value"
        )

        if discount_value is None:
            raise forms.ValidationError(
                "Discount value is required."
            )

        if discount_value <= 0:
            raise forms.ValidationError(
                "Discount value must be greater than zero."
            )

        if discount_type == "PERCENTAGE":

            if discount_value > 100:
                raise forms.ValidationError(
                    "Percentage discount cannot exceed 100%."
                )

        return discount_value

    def clean_minimum_purchase(self):

        minimum_purchase = self.cleaned_data.get(
            "minimum_purchase"
        )

        if minimum_purchase is None:
            return Decimal("0.00")

        if minimum_purchase < 0:
            raise forms.ValidationError(
                "Minimum purchase cannot be negative."
            )

        return minimum_purchase

    def clean_maximum_discount(self):

        maximum_discount = self.cleaned_data.get(
            "maximum_discount"
        )

        if maximum_discount is not None:

            if maximum_discount <= 0:
                raise forms.ValidationError(
                    "Maximum discount must be greater than zero."
                )

        return maximum_discount

    def clean_usage_limit(self):

        usage_limit = self.cleaned_data.get(
            "usage_limit"
        )

        if usage_limit is None:
            raise forms.ValidationError(
                "Usage limit is required."
            )

        if usage_limit <= 0:
            raise forms.ValidationError(
                "Usage limit must be greater than zero."
            )

        return usage_limit

    def clean(self):

        cleaned_data = super().clean()

        discount_type = cleaned_data.get(
            "discount_type"
        )

        discount_value = cleaned_data.get(
            "discount_value"
        )

        maximum_discount = cleaned_data.get(
            "maximum_discount"
        )

        start_date = cleaned_data.get(
            "start_date"
        )

        end_date = cleaned_data.get(
            "end_date"
        )

        minimum_purchase = cleaned_data.get(
            "minimum_purchase"
        )

        if start_date and end_date:

            if end_date <= start_date:

                self.add_error(
                    "end_date",
                    "End date must be after the start date."
                )
    
        if (
            discount_type == "FIXED"
            and discount_value is not None
            and minimum_purchase is not None
        ):

            if discount_value > minimum_purchase:
                self.add_error(
                    "discount_value",
                    "Fixed discount cannot be greater than "
                    "the minimum purchase amount."
                )

        if discount_type == "FIXED":

            cleaned_data["maximum_discount"] = None

        elif discount_type == "PERCENTAGE":

            if (
                maximum_discount is not None
                and maximum_discount <= 0
            ):
                self.add_error(
                    "maximum_discount",
                    "Maximum discount must be greater than zero."
                )

        return cleaned_data