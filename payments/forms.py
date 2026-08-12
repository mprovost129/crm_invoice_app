from django import forms

from .models import Payment, PaymentReversal


class PaymentForm(forms.ModelForm):
    send_receipt = forms.BooleanField(required=False, initial=True)
    receipt_email = forms.EmailField(required=False)

    class Meta:
        model = Payment
        fields = ("amount", "paid_on", "method", "reference", "note")
        widgets = {
            "paid_on": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 2}),
        }


class PaymentReversalForm(forms.ModelForm):
    class Meta:
        model = PaymentReversal
        fields = ("amount", "reason")
        widgets = {"reason": forms.Textarea(attrs={"rows": 2})}
