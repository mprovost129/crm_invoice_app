from django import forms

from .models import ProductService


class ProductServiceForm(forms.ModelForm):
    class Meta:
        model = ProductService
        fields = (
            "name",
            "description",
            "item_type",
            "unit",
            "custom_unit",
            "default_rate",
            "is_taxable",
        )
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def clean(self):
        cleaned_data = super().clean()
        unit = cleaned_data.get("unit")
        custom_unit = (cleaned_data.get("custom_unit") or "").strip()
        if unit == ProductService.Unit.CUSTOM and not custom_unit:
            self.add_error("custom_unit", "Enter the custom unit.")
        elif unit != ProductService.Unit.CUSTOM:
            cleaned_data["custom_unit"] = ""
        return cleaned_data
