from django.contrib import admin, messages

from .models import ReturnRequest, Wallet, WalletTransaction
from .services import approve_return_request, reject_return_request


@admin.action(description="Approve selected returns and refund wallet")
def approve_returns(modeladmin, request, queryset):
    for return_request in queryset:
        try:
            success, message = approve_return_request(return_request.pk, request.user)
        except Exception as exc:
            success, message = False, f"Could not process request #{return_request.pk}: {exc}"
        getattr(messages, "success" if success else "error")(request, message)


@admin.action(description="Reject selected return requests")
def reject_returns(modeladmin, request, queryset):
    for return_request in queryset:
        success, message = reject_return_request(return_request.pk, request.user)
        getattr(messages, "success" if success else "warning")(request, message)


@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "order_item", "status", "requested_at", "reviewed_by", "reviewed_at")
    list_filter = ("status", "requested_at")
    search_fields = ("order_item__order__id", "order_item__product_name", "reason")
    readonly_fields = ("status", "requested_at", "reviewed_at", "reviewed_by")
    actions = (approve_returns, reject_returns)


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "updated_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("balance", "created_at", "updated_at")


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "wallet", "transaction_type", "amount", "balance_after", "order", "created_at")
    list_filter = ("transaction_type", "created_at")
    search_fields = ("wallet__user__username", "description", "order__id")
    readonly_fields = tuple(field.name for field in WalletTransaction._meta.fields)
