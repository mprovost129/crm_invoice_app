from django import template
from django.contrib.auth import get_user_model
from django.db.models import Count, Q

register = template.Library()


@register.simple_tag
def customer_admin_metrics():
    User = get_user_model()
    return User.objects.aggregate(
        total=Count("pk"),
        active=Count("pk", filter=Q(is_active=True)),
        inactive=Count("pk", filter=Q(is_active=False)),
        staff=Count("pk", filter=Q(is_staff=True)),
    )
