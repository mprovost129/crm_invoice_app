from django import forms

from core.models import DocumentSequence

from .models import Business, BusinessSettings, document_prefix_validator

TIMEZONE_CHOICES = [
    ("America/New_York", "Eastern Time"),
    ("America/Chicago", "Central Time"),
    ("America/Denver", "Mountain Time"),
    ("America/Phoenix", "Arizona Time"),
    ("America/Los_Angeles", "Pacific Time"),
    ("America/Anchorage", "Alaska Time"),
    ("Pacific/Honolulu", "Hawaii Time"),
    ("UTC", "UTC"),
]


class BusinessProfileForm(forms.ModelForm):
    website = forms.URLField(required=False, assume_scheme="https")

    class Meta:
        model = Business
        fields = (
            "legal_name",
            "display_name",
            "owner_name",
            "email",
            "phone",
            "website",
            "logo",
            "address_line_1",
            "address_line_2",
            "city",
            "region",
            "postal_code",
            "country_code",
            "default_currency",
            "timezone",
        )
        widgets = {"timezone": forms.Select(choices=TIMEZONE_CHOICES)}

    def clean_country_code(self):
        return self.cleaned_data["country_code"].strip().upper()


class BusinessDefaultsForm(forms.Form):
    estimate_prefix = forms.CharField(
        max_length=12,
        initial="EST-",
        validators=[document_prefix_validator],
    )
    estimate_starting_number = forms.IntegerField(min_value=1, initial=1001)
    invoice_prefix = forms.CharField(
        max_length=12,
        initial="INV-",
        validators=[document_prefix_validator],
    )
    invoice_starting_number = forms.IntegerField(min_value=1, initial=1001)
    default_payment_terms_days = forms.IntegerField(
        min_value=0,
        max_value=365,
        initial=30,
    )
    default_estimate_expiration_days = forms.IntegerField(
        min_value=0,
        max_value=365,
        initial=30,
    )
    default_tax_rate = forms.DecimalField(
        min_value=0,
        max_value=100,
        max_digits=7,
        decimal_places=4,
        initial=0,
    )
    default_invoice_notes = forms.CharField(required=False, widget=forms.Textarea)
    default_invoice_terms = forms.CharField(required=False, widget=forms.Textarea)
    default_estimate_notes = forms.CharField(required=False, widget=forms.Textarea)
    default_estimate_terms = forms.CharField(required=False, widget=forms.Textarea)

    def __init__(self, *args, business=None, **kwargs):
        super().__init__(*args, **kwargs)
        if business is None or self.is_bound:
            return

        settings = BusinessSettings.objects.get(business=business)
        sequences = {
            sequence.document_type: sequence
            for sequence in DocumentSequence.objects.filter(business=business)
        }
        estimate = sequences[DocumentSequence.DocumentType.ESTIMATE]
        invoice = sequences[DocumentSequence.DocumentType.INVOICE]
        self.initial.update(
            {
                "estimate_prefix": settings.estimate_prefix,
                "estimate_starting_number": estimate.next_value,
                "invoice_prefix": settings.invoice_prefix,
                "invoice_starting_number": invoice.next_value,
                "default_payment_terms_days": settings.default_payment_terms_days,
                "default_estimate_expiration_days": (
                    settings.default_estimate_expiration_days
                ),
                "default_tax_rate": settings.default_tax_rate,
                "default_invoice_notes": settings.default_invoice_notes,
                "default_invoice_terms": settings.default_invoice_terms,
                "default_estimate_notes": settings.default_estimate_notes,
                "default_estimate_terms": settings.default_estimate_terms,
            }
        )

    def clean_estimate_prefix(self):
        return self.cleaned_data["estimate_prefix"].strip().upper()

    def clean_invoice_prefix(self):
        return self.cleaned_data["invoice_prefix"].strip().upper()


class BusinessOnboardingForm(BusinessProfileForm, BusinessDefaultsForm):
    """One transaction-ready form for the lightweight onboarding flow."""
