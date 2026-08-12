from django.contrib import admin

from .models import (
    DocumentSnapshot,
    EmailDelivery,
    FileAsset,
    OutboxEvent,
    PublicDocumentLink,
)


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD", "OPTIONS")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DocumentSnapshot)
class DocumentSnapshotAdmin(ReadOnlyAdmin):
    list_display = ("estimate", "business", "version", "content_sha256", "created_at")
    search_fields = ("estimate__number", "business__display_name", "content_sha256")
    readonly_fields = tuple(field.name for field in DocumentSnapshot._meta.fields)


@admin.register(PublicDocumentLink)
class PublicDocumentLinkAdmin(ReadOnlyAdmin):
    list_display = ("estimate", "purpose", "expires_at", "revoked_at", "access_count")
    list_filter = ("purpose", "revoked_at")
    search_fields = ("estimate__number", "business__display_name", "token_digest")
    readonly_fields = tuple(field.name for field in PublicDocumentLink._meta.fields)


@admin.register(FileAsset)
class FileAssetAdmin(ReadOnlyAdmin):
    list_display = ("estimate", "kind", "byte_size", "content_sha256", "created_at")
    search_fields = ("estimate__number", "storage_name", "content_sha256")
    readonly_fields = tuple(field.name for field in FileAsset._meta.fields)


@admin.register(EmailDelivery)
class EmailDeliveryAdmin(ReadOnlyAdmin):
    list_display = ("estimate", "recipient", "status", "sent_at", "created_at")
    list_filter = ("status",)
    search_fields = ("estimate__number", "recipient", "subject")
    readonly_fields = tuple(field.name for field in EmailDelivery._meta.fields)


@admin.register(OutboxEvent)
class OutboxEventAdmin(ReadOnlyAdmin):
    list_display = ("event_type", "status", "attempts", "available_at", "processed_at")
    list_filter = ("status", "event_type")
    search_fields = ("dedupe_key", "last_error")
    readonly_fields = tuple(field.name for field in OutboxEvent._meta.fields)
