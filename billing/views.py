from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from workspaces.mixins import OwnerTenantRequiredMixin

from .models import Plan
from .services import (
    start_subscription_checkout,
    store_platform_webhook,
)
from .stripe_gateway import verify_webhook


class SubscriptionView(OwnerTenantRequiredMixin, TemplateView):
    template_name = "billing/subscription.html"

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "plans": Plan.objects.filter(is_active=True),
            "subscription": self.request.business.workspace.subscription,
        }


class SubscriptionCheckoutView(OwnerTenantRequiredMixin, View):
    def post(self, request):
        try:
            result = start_subscription_checkout(
                actor=request.user,
                plan_code=request.POST.get("plan", ""),
                interval=request.POST.get("interval", ""),
                success_url=(
                    f"{settings.SITE_URL}{reverse('billing:subscription')}?checkout=success"
                ),
                cancel_url=f"{settings.SITE_URL}{reverse('billing:subscription')}",
            )
        except (ImproperlyConfigured, ValidationError) as exc:
            detail = "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
            messages.error(request, detail)
            return redirect("billing:subscription")
        return redirect(result.url)


@csrf_exempt
def platform_webhook(request):
    if request.method != "POST":
        return HttpResponse(status=405)
    try:
        payload = verify_webhook(
            payload=request.body,
            signature=request.headers.get("Stripe-Signature", ""),
            endpoint_secret=settings.STRIPE_PLATFORM_WEBHOOK_SECRET,
        )
        store_platform_webhook(payload=payload)
    except (KeyError, ValueError) as exc:
        return HttpResponseBadRequest(str(exc))
    except Exception:
        return HttpResponse(status=500)
    return HttpResponse(status=200)
