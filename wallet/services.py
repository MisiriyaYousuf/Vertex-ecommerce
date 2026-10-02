from decimal import Decimal, ROUND_DOWN

from django.db import transaction
from django.utils import timezone

from .models import (
    CancellationRequest,
    ReturnRequest,
    Wallet,
    WalletTransaction,
)

CENT = Decimal("0.01")


def get_wallet(user):
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


def refund_amount_for_item(item):
    """Allocate every cent of the paid total proportionally across order items."""
    order = item.order
    items = sorted(order.items.all(), key=lambda row: row.pk)
    item_value = sum((row.item_total for row in items), Decimal("0.00"))
    if not item_value:
        return Decimal("0.00")
    paid_total = max(Decimal("0.00"), order.total_amount).quantize(CENT)
    shares = []
    for row in items:
        exact = paid_total * row.item_total / item_value
        rounded_down = exact.quantize(CENT, rounding=ROUND_DOWN)
        shares.append([row.pk, rounded_down, exact - rounded_down])
    cents_left = int((paid_total - sum((share[1] for share in shares), Decimal("0.00"))) / CENT)
    for share in sorted(shares, key=lambda value: (-value[2], value[0]))[:cents_left]:
        share[1] += CENT
    return next(amount for item_id, amount, _remainder in shares if item_id == item.pk)


def mark_fully_refunded(order):
    if order.payment_status == "Paid" and not order.items.exclude(
        status__in=["Cancelled", "Returned"]
    ).exists():
        order.payment_status = "Refunded"
        order.save(update_fields=["payment_status", "updated_at"])


@transaction.atomic
def debit_wallet_for_order(user, order):
    wallet = Wallet.objects.select_for_update().get(user=user)
    amount = order.total_amount.quantize(CENT)
    if wallet.balance < amount:
        raise ValueError("Your wallet balance is not enough to pay for this order.")
    wallet.balance -= amount
    wallet.save(update_fields=["balance", "updated_at"])
    WalletTransaction.objects.create(
        wallet=wallet,
        transaction_type=WalletTransaction.PURCHASE,
        amount=amount,
        balance_after=wallet.balance,
        description=f"Wallet payment for order #{order.pk}",
        order=order,
    )


@transaction.atomic
def credit_item_refund(item, transaction_type, description):
    existing = WalletTransaction.objects.filter(
        order_item=item, transaction_type=transaction_type
    ).first()
    if existing:
        return existing
    wallet, _ = Wallet.objects.get_or_create(user=item.order.user)
    wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
    amount = refund_amount_for_item(item)
    if amount <= 0:
        return None
    wallet.balance += amount
    wallet.save(update_fields=["balance", "updated_at"])
    return WalletTransaction.objects.create(
        wallet=wallet,
        transaction_type=transaction_type,
        amount=amount,
        balance_after=wallet.balance,
        description=description,
        order=item.order,
        order_item=item,
    )


def restock_item(item):
    if item.variant_id:
        item.variant.quantity += item.quantity
        item.variant.save(update_fields=["quantity", "updated_at"])
    else:
        item.product.quantity += item.quantity
        item.product.save(update_fields=["quantity", "updated_at"])


@transaction.atomic
def approve_return_request(return_request_id, admin_user):
    request = (
        ReturnRequest.objects.select_for_update()
        .select_related("order_item__order", "order_item__product", "order_item__variant")
        .get(pk=return_request_id)
    )
    if request.status != ReturnRequest.PENDING:
        return False, "This return request has already been reviewed."
    item = request.order_item
    order = item.order
    if item.status != "Delivered":
        return False, "The order item is no longer eligible for return."
    if order.payment_status != "Paid":
        return False, "The order is not marked paid, so no refund can be issued."

    item.status = "Returned"
    item.return_reason = request.reason
    item.save(update_fields=["status", "return_reason"])
    restock_item(item)

    from orders.views import update_status
    update_status(order)
    credit_item_refund(
        item,
        WalletTransaction.RETURN_REFUND,
        f"Approved return refund for order #{order.pk}",
    )
    mark_fully_refunded(order)
    request.status = ReturnRequest.APPROVED
    request.reviewed_by = admin_user
    request.reviewed_at = timezone.now()
    request.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    return True, f"Return for order #{order.pk} approved and refunded to wallet."


@transaction.atomic
def reject_return_request(return_request_id, admin_user, note=""):
    request = ReturnRequest.objects.select_for_update().get(pk=return_request_id)
    if request.status != ReturnRequest.PENDING:
        return False, "This return request has already been reviewed."
    request.status = ReturnRequest.REJECTED
    request.reviewed_by = admin_user
    request.reviewed_at = timezone.now()
    request.review_note = note
    request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note"])
    return True, f"Return request for order item #{request.order_item_id} rejected."


@transaction.atomic
def approve_cancellation_request(cancellation_request_id, admin_user):
    request = (
        CancellationRequest.objects.select_for_update()
        .select_related(
            "order_item__order",
            "order_item__product",
            "order_item__variant",
        )
        .get(pk=cancellation_request_id)
    )
    if request.status != CancellationRequest.PENDING:
        return False, "This cancellation request has already been reviewed."

    item = request.order_item
    order = item.order
    if item.status == "Delivered":
        request.status = CancellationRequest.REJECTED
        request.reviewed_by = admin_user
        request.reviewed_at = timezone.now()
        request.review_note = "A delivered item cannot be cancelled or refunded."
        request.save(
            update_fields=["status", "reviewed_by", "reviewed_at", "review_note"]
        )
        return False, "Cancellation rejected: delivered items cannot be refunded."

    if item.status in ["Cancelled", "Returned"]:
        return False, "This order item has already reached a final status."

    item.status = "Cancelled"
    item.cancellation_reason = request.reason
    item.save(update_fields=["status", "cancellation_reason"])
    restock_item(item)

    from orders.views import update_status

    update_status(order)
    if order.payment_status == "Paid":
        credit_item_refund(
            item,
            WalletTransaction.CANCEL_REFUND,
            f"Approved cancellation refund for order #{order.pk}",
        )
        mark_fully_refunded(order)

    request.status = CancellationRequest.APPROVED
    request.reviewed_by = admin_user
    request.reviewed_at = timezone.now()
    request.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    return True, f"Cancellation for order #{order.pk} approved and refunded to wallet."


@transaction.atomic
def reject_cancellation_request(cancellation_request_id, admin_user, note=""):
    request = CancellationRequest.objects.select_for_update().get(
        pk=cancellation_request_id
    )
    if request.status != CancellationRequest.PENDING:
        return False, "This cancellation request has already been reviewed."

    request.status = CancellationRequest.REJECTED
    request.reviewed_by = admin_user
    request.reviewed_at = timezone.now()
    request.review_note = note
    request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note"])
    return True, f"Cancellation request for order item #{request.order_item_id} rejected."
