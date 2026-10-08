from django import forms
from django.core.exceptions import ValidationError


class SalesReportForm(forms.Form):

    REPORT_TYPE_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("yearly", "Yearly"),
        ("custom", "Custom Date"),
    ]

    report_type = forms.ChoiceField(
        choices=REPORT_TYPE_CHOICES,
        initial="daily",
        widget=forms.Select(
            attrs={
                "class": "form-select",
                "id": "report_type",
            }
        ),
    )

    date = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "form-control",
                "id": "report_date",
            }
        ),
    )

    month = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "type": "month",
                "class": "form-control",
                "id": "report_month",
            }
        ),
    )

    year = forms.IntegerField(
        required=False,
        min_value=2000,
        max_value=2100,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "id": "report_year",
            }
        ),
    )

    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "form-control",
                "id": "start_date",
            }
        ),
    )

    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "form-control",
                "id": "end_date",
            }
        ),
    )

    def clean(self):

        cleaned_data = super().clean()

        report_type = cleaned_data.get("report_type")

        date = cleaned_data.get("date")
        month = cleaned_data.get("month")
        year = cleaned_data.get("year")

        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if report_type == "daily":

            if not date:
                raise ValidationError(
                    "Please select a date for the daily report."
                )

        elif report_type == "weekly":

            if not date:
                raise ValidationError(
                    "Please select a date for the weekly report."
                )

        elif report_type == "monthly":

            if not month:
                raise ValidationError(
                    "Please select a month for the monthly report."
                )

        elif report_type == "yearly":

            if not year:
                raise ValidationError(
                    "Please select a year for the yearly report."
                )

        elif report_type == "custom":

            if not start_date:
                raise ValidationError(
                    "Please select a start date."
                )

            if not end_date:
                raise ValidationError(
                    "Please select an end date."
                )

            if start_date > end_date:
                raise ValidationError(
                    "Start date cannot be later than end date."
                )

        return cleaned_data