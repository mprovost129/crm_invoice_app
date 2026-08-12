from django.db.models import Q

from activity.models import ActivityEvent

from .models import Contact, ContactNote


def contacts_for_business(*, business, search="", status=""):
    contacts = Contact.objects.for_business(business)
    if status in Contact.Status.values:
        contacts = contacts.filter(status=status)
    if search:
        contacts = contacts.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(company_name__icontains=search)
            | Q(email__icontains=search)
            | Q(phone__icontains=search)
        )
    return contacts


def contact_for_business(*, business, contact_id):
    return Contact.objects.for_business(business).filter(pk=contact_id).first()


def contact_notes(*, business, contact):
    return ContactNote.objects.for_business(business).filter(contact=contact)


def contact_activity(*, business, contact):
    return ActivityEvent.objects.for_business(business).filter(contact=contact)
