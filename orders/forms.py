from django import forms

from users.models import Address


class CheckoutForm(forms.Form):

    address = forms.ModelChoiceField(
        queryset=Address.objects.none(),
        empty_label=None,
        widget=forms.RadioSelect
    )

    payment_method = forms.ChoiceField(
        choices=[
            ("COD", "Cash on Delivery")
        ],
        widget=forms.RadioSelect
    )

    def __init__(self, user, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.fields["address"].queryset = Address.objects.filter(
            user=user
        ).order_by("-is_default", "-created_at")