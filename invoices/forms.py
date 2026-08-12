from decimal import Decimal

from django import forms

from catalog.models import ProductService
from crm.models import Contact

from .models import Invoice, InvoiceLineItem


class InvoiceForm(forms.ModelForm):
    contact = forms.ModelChoiceField(queryset=Contact.objects.none())

    class Meta:
        model = Invoice
        fields = (
            "contact",
            "due_date",
            "discount_type",
            "discount_value",
            "deposit_required",
            "notes",
            "terms",
        )
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
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
                    "notes": business.settings.default_invoice_notes,
                    "terms": business.settings.default_invoice_terms,
                }
            )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("discount_type") == Invoice.AmountType.NONE:
            cleaned_data["discount_value"] = Decimal("0")
        return cleaned_data

    def service_data(self):
        return {**self.cleaned_data, "contact_id": self.cleaned_data["contact"].pk}


class InvoiceLineForm(forms.ModelForm):
    source_catalog_item = forms.ModelChoiceField(
        queryset=ProductService.objects.none(),
        required=False,
        label="Catalog item (optional)",
    )
    name = forms.CharField(max_length=255, required=False)
    unit = forms.CharField(max_length=40, required=False)

    class Meta:
        model = InvoiceLineItem
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


class InvoiceEmailForm(forms.Form):
    recipient = forms.EmailField()


class VoidInvoiceForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
