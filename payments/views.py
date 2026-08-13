import hashlib

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from billing.entitlements import Feature, entitlements_for_business, require_feature
from communications.links import create_public_link, resolve_public_link
from communications.models import PublicDocumentLink
from invoices.models import Invoice
from workspaces.mixins import OwnerTenantRequiredMixin

from .models import ConnectedAccount
from .online_services import (
    onboarding_url,
    refresh_connected_account,
    start_invoice_checkout,
    store_connect_webhook,
)
from .stripe_gateway import verify_webhook


class PaymentSettingsView(OwnerTenantRequiredMixin, TemplateView):
    template_name = "payments/settings.html"

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "connected_account": ConnectedAccount.objects.filter(
                business=self.request.business
            ).first(),
            "online_payments_allowed": entitlements_for_business(
                business=self.request.business
            ).allows(Feature.ONLINE_PAYMENTS),
        }


class ConnectOnboardingView(OwnerTenantRequiredMixin, View):
    def post(self, request):
        try:
            require_feature(business=request.business, feature=Feature.ONLINE_PAYMENTS)
            url = onboarding_url(
                actor=request.user,
                business_id=request.business.pk,
                refresh_url=(
                    f"{settings.SITE_URL}{reverse('payments:connect-refresh')}"
                ),
                return_url=f"{settings.SITE_URL}{reverse('payments:connect-return')}",
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return redirect("payments:settings")
        return redirect(url)


class ConnectRefreshView(OwnerTenantRequiredMixin, View):
    def get(self, request):
        return ConnectOnboardingView().post(request)


class ConnectReturnView(OwnerTenantRequiredMixin, View):
    def get(self, request):
        try:
            account = refresh_connected_account(
                actor=request.user, business_id=request.business.pk
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            if account.is_ready:
                messages.success(request, "Online payments are ready.")
            else:
                messages.info(
                    request,
                    "Stripe onboarding was saved, but more information may be required.",
                )
        return redirect("payments:settings")


class CreateInvoicePaymentLinkView(OwnerTenantRequiredMixin, View):
    def post(self, request, invoice_id):
        invoice = (
            Invoice.objects.for_business(request.business).filter(pk=invoice_id).first()
        )
        if invoice is None:
            raise Http404("Invoice not found.")
        try:
            require_feature(business=request.business, feature=Feature.ONLINE_PAYMENTS)
            if not ConnectedAccount.objects.filter(
                business=request.business, status=ConnectedAccount.Status.READY
            ).exists():
                raise ValidationError("Finish payment onboarding first.")
            if invoice.status in {Invoice.Status.DRAFT, Invoice.Status.VOID}:
                raise ValidationError("Only open issued invoices can be paid online.")
            if invoice.balance_due <= 0:
                raise ValidationError("This invoice is already paid.")
            _, token = create_public_link(
                invoice=invoice, purpose=PublicDocumentLink.Purpose.PAY
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return redirect("invoices:detail", invoice_id=invoice.pk)
        return redirect("payments:public-payment", token=token)


@never_cache
def public_payment(request, token):
    link = resolve_public_link(
        raw_token=token,
        allowed_purposes=(PublicDocumentLink.Purpose.PAY,),
        target="invoice",
    )
    invoice = link.invoice
    if request.method == "POST":
        identity = request.META.get("REMOTE_ADDR", "unknown")
        digest = hashlib.sha256(
            f"{identity}:{link.token_digest}".encode("utf-8")
        ).hexdigest()
        key = f"public-payment-rate:{digest}"
        if cache.add(key, 1, timeout=900):
            attempts = 1
        else:
            try:
                attempts = cache.incr(key)
            except ValueError:
                cache.set(key, 1, timeout=900)
                attempts = 1
        if attempts > settings.PUBLIC_PAYMENT_ATTEMPT_LIMIT:
            return HttpResponse("Too many payment attempts.", status=429)
        try:
            attempt = start_invoice_checkout(link=link, raw_token=token)
        except ValidationError as exc:
            return render(
                request,
                "payments/public_payment.html",
                {"invoice": invoice, "token": token, "error": "; ".join(exc.messages)},
                status=400,
            )
        return redirect(attempt.checkout_url)
    response = render(
        request,
        "payments/public_payment.html",
        {"invoice": invoice, "token": token},
    )
    response["Referrer-Policy"] = "no-referrer"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


@never_cache
def payment_return(request):
    response = render(request, "payments/payment_return.html")
    response["Referrer-Policy"] = "no-referrer"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


@csrf_exempt
def connect_webhook(request):
    if request.method != "POST":
        return HttpResponse(status=405)
    try:
        payload = verify_webhook(
            payload=request.body,
            signature=request.headers.get("Stripe-Signature", ""),
            endpoint_secret=settings.STRIPE_CONNECT_WEBHOOK_SECRET,
        )
        store_connect_webhook(payload=payload)
    except (KeyError, ValueError) as exc:
        return HttpResponseBadRequest(str(exc))
    except Exception:
        return HttpResponse(status=500)
    return HttpResponse(status=200)
