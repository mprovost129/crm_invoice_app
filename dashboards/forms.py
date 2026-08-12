from django import forms


class ReportPeriodForm(forms.Form):
    start = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
    end = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start")
        end = cleaned_data.get("end")
        if start and end and end < start:
            raise forms.ValidationError("End date cannot be before start date.")
        if start and end and (end - start).days > 366:
            raise forms.ValidationError(
                "Choose a reporting period of one year or less."
            )
        return cleaned_data
