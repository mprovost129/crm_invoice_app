from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect
from django.views import View
from django.views.generic import FormView, ListView

from workspaces.mixins import OwnerTenantRequiredMixin

from .forms import ProductServiceForm
from .models import ProductService
from .selectors import catalog_item_for_business, catalog_items_for_business
from .services import (
    archive_catalog_item,
    create_catalog_item,
    restore_catalog_item,
    update_catalog_item,
)


class CatalogListView(OwnerTenantRequiredMixin, ListView):
    template_name = "catalog/productservice_list.html"
    context_object_name = "items"
    paginate_by = 25

    def get_queryset(self):
        return catalog_items_for_business(
            business=self.request.business,
            search=self.request.GET.get("q", "").strip(),
            item_type=self.request.GET.get("type", "").strip(),
            status=self.request.GET.get("status", "active").strip(),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "search": self.request.GET.get("q", "").strip(),
                "type_filter": self.request.GET.get("type", "").strip(),
                "status_filter": self.request.GET.get("status", "active").strip(),
                "type_choices": ProductService.ItemType.choices,
            }
        )
        return context


class CatalogCreateView(OwnerTenantRequiredMixin, FormView):
    template_name = "catalog/productservice_form.html"
    form_class = ProductServiceForm

    def form_valid(self, form):
        create_catalog_item(
            actor=self.request.user,
            business_id=self.request.business.pk,
            data=form.cleaned_data,
        )
        messages.success(self.request, "Catalog item created.")
        return redirect("catalog:item-list")


class CatalogObjectMixin:
    item = None

    def dispatch(self, request, *args, **kwargs):
        self.item = catalog_item_for_business(
            business=request.business,
            item_id=kwargs["item_id"],
        )
        if self.item is None:
            raise Http404("Catalog item not found.")
        return super().dispatch(request, *args, **kwargs)


class CatalogUpdateView(
    OwnerTenantRequiredMixin,
    CatalogObjectMixin,
    FormView,
):
    template_name = "catalog/productservice_form.html"
    form_class = ProductServiceForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.item
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["item"] = self.item
        return context

    def form_valid(self, form):
        update_catalog_item(
            actor=self.request.user,
            business_id=self.request.business.pk,
            item_id=self.item.pk,
            data=form.cleaned_data,
        )
        messages.success(self.request, "Catalog item updated.")
        return redirect("catalog:item-list")


class CatalogStatusView(OwnerTenantRequiredMixin, CatalogObjectMixin, View):
    actions = {
        "archive": archive_catalog_item,
        "restore": restore_catalog_item,
    }

    def post(self, request, *args, **kwargs):
        service = self.actions.get(kwargs["action"])
        if service is None:
            raise Http404("Catalog action not found.")
        try:
            service(
                actor=request.user,
                business_id=request.business.pk,
                item_id=self.item.pk,
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "Catalog status updated.")
        return redirect("catalog:item-list")
