from django import forms

from .models import Contact, ContactNote


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = (
            "first_name",
            "last_name",
            "company_name",
            "email",
            "phone",
            "address_line_1",
            "address_line_2",
            "city",
            "region",
            "postal_code",
            "country_code",
            "notes",
        )
        widgets = {"notes": forms.Textarea(attrs={"rows": 4})}

    def clean_country_code(self):
        return self.cleaned_data["country_code"].strip().upper()


class ContactCreateForm(ContactForm):
    initial_status = forms.ChoiceField(
        label="Start as",
        choices=(
            (Contact.Status.LEAD, "Lead"),
            (Contact.Status.CLIENT, "Client"),
        ),
        initial=Contact.Status.LEAD,
    )


class ContactNoteForm(forms.ModelForm):
    class Meta:
        model = ContactNote
        fields = ("body",)
        widgets = {
            "body": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Add an internal note"}
            )
        }

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if not body:
            raise forms.ValidationError("Enter a note.")
        return body
