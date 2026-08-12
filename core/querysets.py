from django.db import models


class BusinessOwnedQuerySet(models.QuerySet):
    """Reusable explicit tenant scope for future business-owned models."""

    def for_business(self, business):
        if business is None:
            return self.none()
        return self.filter(business=business)
