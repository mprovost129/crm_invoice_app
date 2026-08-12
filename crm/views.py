from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django.views.generic import FormView, ListView, TemplateView

from workspaces.mixins import OwnerTenantRequiredMixin

from .forms import ContactCreateForm, ContactForm, ContactNoteForm
from .models import Contact
from .selectors import (
    contact_activity,
    contact_for_business,
    contact_notes,
    contacts_for_business,
)
from .services import (
    add_contact_note,
    archive_contact,
    create_contact,
    promote_contact_to_client,
    restore_contact,
    update_contact,
)


class ContactListView(OwnerTenantRequiredMixin, ListView):
    template_name = "crm/contact_list.html"
    context_object_name = "contacts"
    paginate_by = 25

    def get_queryset(self):
        return contacts_for_business(
            business=self.request.business,
            search=self.request.GET.get("q", "").strip(),
            status=self.request.GET.get("status", "").strip(),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "search": self.request.GET.get("q", "").strip(),
                "status_filter": self.request.GET.get("status", "").strip(),
                "status_choices": Contact.Status.choices,
            }
        )
        return context


class ContactCreateView(OwnerTenantRequiredMixin, FormView):
    template_name = "crm/contact_form.html"
    form_class = ContactCreateForm

    def form_valid(self, form):
        contact = create_contact(
            actor=self.request.user,
            business_id=self.request.business.pk,
            data=form.cleaned_data,
        )
        messages.success(self.request, "Contact created.")
        return redirect("crm:contact-detail", contact_id=contact.pk)


class ContactObjectMixin:
    contact = None

    def dispatch(self, request, *args, **kwargs):
        self.contact = contact_for_business(
            business=request.business,
            contact_id=kwargs["contact_id"],
        )
        if self.contact is None:
            raise Http404("Contact not found.")
        return super().dispatch(request, *args, **kwargs)


class ContactDetailView(
    OwnerTenantRequiredMixin,
    ContactObjectMixin,
    TemplateView,
):
    template_name = "crm/contact_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "contact": self.contact,
                "notes": contact_notes(
                    business=self.request.business,
                    contact=self.contact,
                ),
                "activity_events": contact_activity(
                    business=self.request.business,
                    contact=self.contact,
                )[:50],
                "note_form": ContactNoteForm(),
                "financial_summary": {
                    "estimates": 0,
                    "invoices": 0,
                    "payments": 0,
                    "outstanding": None,
                },
            }
        )
        return context


class ContactUpdateView(
    OwnerTenantRequiredMixin,
    ContactObjectMixin,
    FormView,
):
    template_name = "crm/contact_form.html"
    form_class = ContactForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.contact
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["contact"] = self.contact
        return context

    def form_valid(self, form):
        contact = update_contact(
            actor=self.request.user,
            business_id=self.request.business.pk,
            contact_id=self.contact.pk,
            data=form.cleaned_data,
        )
        messages.success(self.request, "Contact updated.")
        return redirect("crm:contact-detail", contact_id=contact.pk)


class ContactStatusView(OwnerTenantRequiredMixin, ContactObjectMixin, View):
    actions = {
        "promote": promote_contact_to_client,
        "archive": archive_contact,
        "restore": restore_contact,
    }

    def post(self, request, *args, **kwargs):
        action = kwargs["action"]
        service = self.actions.get(action)
        if service is None:
            raise Http404("Contact action not found.")
        try:
            contact = service(
                actor=request.user,
                business_id=request.business.pk,
                contact_id=self.contact.pk,
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            contact = self.contact
        else:
            messages.success(request, "Contact status updated.")
        return redirect("crm:contact-detail", contact_id=contact.pk)


class ContactNoteCreateView(OwnerTenantRequiredMixin, ContactObjectMixin, View):
    def post(self, request, *args, **kwargs):
        form = ContactNoteForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Enter a note before saving.")
        else:
            add_contact_note(
                actor=request.user,
                business_id=request.business.pk,
                contact_id=self.contact.pk,
                body=form.cleaned_data["body"],
            )
            messages.success(request, "Note added.")
        return redirect(
            f"{reverse('crm:contact-detail', kwargs={'contact_id': self.contact.pk})}#notes"
        )
