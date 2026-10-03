from django import forms

from products.models import Product
from customadmin.models import Category

from .models import CategoryOffer, ProductOffer, ReferralOffer


class BootstrapModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        for name in ("is_active",):
            if name in self.fields:
                self.fields[name].widget.attrs["class"] = "form-check-input"


class ProductOfferForm(BootstrapModelForm):
    class Meta:
        model = ProductOffer
        fields = ["name", "product", "discount_percentage", "start_date", "end_date", "is_active"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "discount_percentage": forms.NumberInput(attrs={"min": "0.01", "max": "100", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(is_active=True, is_deleted=False).order_by("name")


class CategoryOfferForm(BootstrapModelForm):
    class Meta:
        model = CategoryOffer
        fields = ["name", "category", "discount_percentage", "start_date", "end_date", "is_active"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "discount_percentage": forms.NumberInput(attrs={"min": "0.01", "max": "100", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(is_trashed=False).order_by("name")


class ReferralOfferForm(BootstrapModelForm):
    class Meta:
        model = ReferralOffer
        fields = [
            "name", "discount_type", "discount_value", "minimum_purchase",
            "maximum_discount", "valid_days", "start_date", "end_date", "is_active",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "discount_value": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "minimum_purchase": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "maximum_discount": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "valid_days": forms.NumberInput(attrs={"min": "1"}),
        }
