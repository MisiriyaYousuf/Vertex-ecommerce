from django.conf import settings
from django.db import models
from django.db.models import Q


class Wallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet",
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet for {self.user} (₹{self.balance})"


class WalletTransaction(models.Model):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"
    CANCEL_REFUND = "CANCEL_REFUND"
    RETURN_REFUND = "RETURN_REFUND"
    PURCHASE = "PURCHASE"
    TYPE_CHOICES = [
        (CREDIT, "Credit"),
        (DEBIT, "Debit"),
        (CANCEL_REFUND, "Cancellation refund"),
        (RETURN_REFUND, "Return refund"),
        (PURCHASE, "Wallet purchase"),
    ]

    wallet = models.ForeignKey(
        Wallet, on_delete=models.CASCADE, related_name="transactions"
    )
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255)
    order = models.ForeignKey(
        "orders.Order", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="wallet_transactions",
    )
    order_item = models.ForeignKey(
        "orders.OrderItem", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="wallet_transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "transaction_type"],
                condition=Q(order__isnull=False, transaction_type="PURCHASE"),
                name="wallet_unique_purchase_per_order",
            ),
            models.UniqueConstraint(
                fields=["order_item", "transaction_type"],
                condition=Q(
                    order_item__isnull=False,
                    transaction_type__in=["CANCEL_REFUND", "RETURN_REFUND"],
                ),
                name="wallet_unique_refund_per_item_type",
            ),
        ]

    def __str__(self):
        return f"{self.get_transaction_type_display()} ₹{self.amount}"


class ReturnRequest(models.Model):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    STATUS_CHOICES = [
        (PENDING, "Pending review"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
    ]

    order_item = models.OneToOneField(
        "orders.OrderItem", on_delete=models.CASCADE,
        related_name="return_request",
    )
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reviewed_return_requests",
    )
    review_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self):
        return f"Return for order item #{self.order_item_id} ({self.status})"


class CancellationRequest(models.Model):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    STATUS_CHOICES = [
        (PENDING, "Pending review"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
    ]

    order_item = models.OneToOneField(
        "orders.OrderItem",
        on_delete=models.CASCADE,
        related_name="cancellation_request",
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=PENDING,
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_cancellation_requests",
    )
    review_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self):
        return f"Cancellation for order item #{self.order_item_id} ({self.status})"
