from django.core.exceptions import ValidationError
from django.db import transaction

from .models import DocumentSequence


@transaction.atomic
def allocate_document_number(*, business, document_type):
    sequence = (
        DocumentSequence.objects.select_for_update()
        .filter(business=business, document_type=document_type)
        .first()
    )
    if sequence is None:
        raise ValidationError("The document number sequence is not configured.")
    number = f"{sequence.prefix}{sequence.next_value:0{sequence.padding_width}d}"
    sequence.next_value += 1
    sequence.save(update_fields=("next_value", "updated_at"))
    return number
