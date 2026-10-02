from django import forms


class ReturnRequestForm(forms.Form):
    RETURN_REASONS = [
        ("Product damaged", "Product damaged"),
        ("Wrong product received", "Wrong product received"),
        ("Product is defective", "Product is defective"),
        ("Product does not match description", "Product does not match description"),
        ("Received different size or color", "Received different size or color"),
        ("Changed my mind", "Changed my mind"),
    ]
    return_reason = forms.ChoiceField(choices=[("", "Select a reason"), *RETURN_REASONS])
