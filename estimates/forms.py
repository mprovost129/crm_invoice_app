from decimal import Decimal

from django import forms

from catalog.models import ProductService
from crm.models import Contact

from .models import Estimate, EstimateAcceptance, EstimateLineItem


class EstimateForm(forms.ModelForm):
    contact = forms.ModelChoiceField(queryset=Contact.objects.none())

    class Meta:
        model = Estimate
        fields = (
            "contact",
            "expiration_date",
            "discount_type",
            "discount_value",
            "deposit_type",
            "deposit_value",
            "requires_acceptance",
            "notes",
            "terms",
        )
        widgets = {
            "expiration_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "terms": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, business, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance._state.adding:
            self.instance.business = business
        self.fields["contact"].queryset = Contact.objects.for_business(
            business
        ).active()
        if not self.is_bound and self.instance._state.adding:
            self.initial.update(
                {
                    "notes": business.settings.default_estimate_notes,
                    "terms": business.settings.default_estimate_terms,
                }
            )

    def clean(self):
        cleaned_data = super().clean()
        for type_field, value_field in (
            ("discount_type", "discount_value"),
            ("deposit_type", "deposit_value"),
        ):
            if cleaned_data.get(type_field) == Estimate.AmountType.NONE:
                cleaned_data[value_field] = Decimal("0")
        return cleaned_data

    def service_data(self):
        return {
            **self.cleaned_data,
            "contact_id": self.cleaned_data["contact"].pk,
        }


class EstimateLineForm(forms.ModelForm):
    source_catalog_item = forms.ModelChoiceField(
        queryset=ProductService.objects.none(),
        required=False,
        label="Catalog item (optional)",
    )
    name = forms.CharField(max_length=255, required=False)
    unit = forms.CharField(max_length=40, required=False)

    class Meta:
        model = EstimateLineItem
        fields = (
            "source_catalog_item",
            "name",
            "description",
            "unit",
            "quantity",
            "unit_rate",
            "is_taxable",
            "tax_rate",
        )
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, business, catalog_item=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.business = business
        if self.instance._state.adding:
            self.instance.business = business
        self.fields[
            "source_catalog_item"
        ].queryset = ProductService.objects.for_business(business).active()
        if not self.is_bound:
            self.initial.setdefault("quantity", Decimal("1"))
            self.initial.setdefault("tax_rate", business.settings.default_tax_rate)
            if catalog_item:
                self.initial.update(
                    {
                        "source_catalog_item": catalog_item,
                        "name": catalog_item.name,
                        "description": catalog_item.description,
                        "unit": catalog_item.unit_label,
                        "unit_rate": catalog_item.default_rate,
                        "is_taxable": catalog_item.is_taxable,
                    }
                )

    def clean(self):
        cleaned_data = super().clean()
        item = cleaned_data.get("source_catalog_item")
        if item:
            cleaned_data["name"] = cleaned_data.get("name") or item.name
            cleaned_data["description"] = (
                cleaned_data.get("description") or item.description
            )
            cleaned_data["unit"] = cleaned_data.get("unit") or item.unit_label
        if not (cleaned_data.get("name") or "").strip():
            self.add_error("name", "Enter a line-item name or select a catalog item.")
        if not cleaned_data.get("is_taxable"):
            cleaned_data["tax_rate"] = Decimal("0")
        return cleaned_data

    def service_data(self):
        return {
            **self.cleaned_data,
            "source_catalog_item_id": (
                self.cleaned_data["source_catalog_item"].pk
                if self.cleaned_data.get("source_catalog_item")
                else None
            ),
        }


class EstimateEmailForm(forms.Form):
    recipient = forms.EmailField()


class ManualAcceptanceForm(forms.Form):
    method = forms.ChoiceField(
        choices=(
            (EstimateAcceptance.Method.EMAIL, "Email"),
            (EstimateAcceptance.Method.PHONE, "Phone"),
            (EstimateAcceptance.Method.IN_PERSON, "In person"),
            (EstimateAcceptance.Method.OTHER, "Other"),
        )
    )
    accepted_by_name = forms.CharField(max_length=255, required=False)
    evidence_note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )


class PublicAcceptanceForm(forms.Form):
    accepted_by_name = forms.CharField(max_length=255)
    accepted_by_email = forms.EmailField(required=False)
    confirm = forms.BooleanField(
        label="I am authorized to accept this estimate and agree to its terms."
    )


class PublicDeclineForm(forms.Form):
    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
