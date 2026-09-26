import re
from django import forms
from .models import Category
from products.models import Product, ProductVariant

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

        # Required fields
        self.fields["sale_price"].required = True
        self.fields["discount_price"].required = False
        self.fields["color"].required = True
        self.fields["size"].required = True
        self.fields["product_code"].required = True
        self.fields["quantity"].required = True

    # =====================================================
    # SALE PRICE
    # =====================================================

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

    # =====================================================
    # DISCOUNT PRICE
    # =====================================================

    def clean_discount_price(self):

        discount_price = self.cleaned_data.get("discount_price")

        if discount_price in ("", None):
            return None

        if discount_price <= 0:
            raise forms.ValidationError(
                "Variant discount price must be greater than zero."
            )

        return discount_price

    # =====================================================
    # COLOR
    # =====================================================

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

    # =====================================================
    # SIZE
    # =====================================================

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

    # =====================================================
    # PRODUCT CODE
    # =====================================================

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

        # ---------------------------------------------
        # Check other variants
        # ---------------------------------------------

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

        # ---------------------------------------------
        # Check base products
        # ---------------------------------------------

        existing_product = Product.objects.filter(
            product_code__iexact=product_code
        )

        if existing_product.exists():
            raise forms.ValidationError(
                "This product code is already used by a base product."
            )

        return product_code

    # =====================================================
    # QUANTITY
    # =====================================================

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

    # =====================================================
    # FINAL VARIANT VALIDATION
    # =====================================================

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
