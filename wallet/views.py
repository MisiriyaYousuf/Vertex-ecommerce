from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from .services import get_wallet


@login_required
def wallet_home(request):
    wallet = get_wallet(request.user)
    transactions = Paginator(wallet.transactions.select_related("order", "order_item"), 20)
    return render(request, "wallet_home.html", {
        "wallet": wallet,
        "transactions": transactions.get_page(request.GET.get("page")),
    })
