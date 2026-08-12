from zoneinfo import ZoneInfo

from django.http import Http404
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView

from communications.models import EmailDelivery, Notification
from workspaces.mixins import OwnerTenantRequiredMixin

from .exports import clients_csv, contacts_csv, invoices_csv, payments_csv
from .forms import ReportPeriodForm
from .selectors import (
    communication_alerts,
    report_summary,
)


class ReportsView(OwnerTenantRequiredMixin, TemplateView):
    template_name = "dashboards/reports.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate(timezone=ZoneInfo(self.request.business.timezone))
        initial = {"start": today.replace(day=1), "end": today}
        form = ReportPeriodForm(self.request.GET or None, initial=initial)
        context["form"] = form
        if form.is_bound and form.is_valid():
            start = form.cleaned_data["start"]
            end = form.cleaned_data["end"]
        elif not form.is_bound:
            start = initial["start"]
            end = initial["end"]
        else:
            start = end = None
        if start and end:
            context["report"] = report_summary(
                business=self.request.business,
                start=start,
                end=end,
                today=today,
            )
        return context


class CommunicationsView(OwnerTenantRequiredMixin, ListView):
    template_name = "dashboards/communications.html"
    context_object_name = "deliveries"
    paginate_by = 25

    def get_queryset(self):
        deliveries = EmailDelivery.objects.filter(
            business=self.request.business
        ).select_related("estimate", "invoice", "payment__invoice")
        status = self.request.GET.get("status", "").strip()
        kind = self.request.GET.get("kind", "").strip()
        search = self.request.GET.get("q", "").strip()
        if status in EmailDelivery.Status.values:
            deliveries = deliveries.filter(status=status)
        if kind in EmailDelivery.Kind.values:
            deliveries = deliveries.filter(kind=kind)
        if search:
            from django.db.models import Q

            deliveries = deliveries.filter(
                Q(recipient__icontains=search)
                | Q(subject__icontains=search)
                | Q(estimate__number__icontains=search)
                | Q(invoice__number__icontains=search)
                | Q(payment__invoice__number__icontains=search)
            )
        return deliveries

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "alerts": communication_alerts(business=self.request.business),
            "status_choices": EmailDelivery.Status.choices,
            "kind_choices": EmailDelivery.Kind.choices,
            "status_filter": self.request.GET.get("status", "").strip(),
            "kind_filter": self.request.GET.get("kind", "").strip(),
            "search": self.request.GET.get("q", "").strip(),
        }


class NotificationReadView(OwnerTenantRequiredMixin, View):
    def post(self, request, notification_id):
        notification = Notification.objects.filter(
            pk=notification_id,
            business=request.business,
            recipient=request.user,
        ).first()
        if notification is None:
            raise Http404("Notification not found.")
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=("read_at", "updated_at"))
        target_path = notification.target_path
        if target_path and target_path.startswith("/app/"):
            return redirect(target_path)
        return redirect("workspaces:dashboard")


class ExportView(OwnerTenantRequiredMixin, View):
    exporters = {
        "clients": clients_csv,
        "contacts": contacts_csv,
        "invoices": invoices_csv,
        "payments": payments_csv,
    }

    def get(self, request, export_type):
        exporter = self.exporters.get(export_type)
        if exporter is None:
            raise Http404("Export not found.")
        return exporter(business=request.business)
