from django.db import models


class TimeStampedModel(models.Model):
    """Optional abstract base for the common created/updated timestamp pattern."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
