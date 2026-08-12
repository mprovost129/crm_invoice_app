# Users / customer architecture

This starter uses a custom email-first `users.User` model from day one.

## Rules for every project app

Never import `users.User` directly from another reusable/project app for a model relationship. Use:

```python
from django.conf import settings

user = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.CASCADE,
    related_name="projects",
)
```

For runtime code that needs the User class, use:

```python
from django.contrib.auth import get_user_model
User = get_user_model()
```

Avoid `user.user`. If a model already has a field named `user`, that object is the
authenticated user. Use `user.account_profile` for supplementary owner metadata.
Business identity belongs to the future tenant `Business` model, and customer/client
data belongs to the future CRM `Contact` model. `AccountProfile` replaces neither.

## Customer-centric admin

The admin home page starts with customer search. The User change page is the customer support hub and automatically lists reverse relations from project models that point directly to `AUTH_USER_MODEL`.

For high-value project records such as `Subscription`, add a dedicated inline to `users.admin.UserAdmin` when you want those fields editable directly from the customer page. Keep subscription actions (cancel, sync, refund, etc.) as explicit service-layer/admin actions rather than raw status edits.
