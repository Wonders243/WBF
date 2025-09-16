import os
import requests
from django.conf import settings


BASE_URL = "https://api.flutterwave.com/v3"


def _headers():
    return {
        "Authorization": f"Bearer {settings.FLW_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def create_payment_link(*, tx_ref: str, amount: str | float, currency: str, redirect_url: str,
                        customer_name: str = "", customer_email: str = "",
                        payment_options: str = "mpesa,mobilemoneyghana,mobilemoneyzambia,mobilemoneyuganda,banktransfer,card,ussd"):
    """
    Create a Flutterwave Standard Checkout payment and return redirect link.
    """
    payload = {
        "tx_ref": tx_ref,
        "amount": str(amount),
        "currency": currency,
        "redirect_url": redirect_url,
        "payment_options": payment_options,
        "customer": {
            "name": customer_name or "",
            "email": customer_email or "",
        },
        "customizations": {
            "title": "Don — Bamu Wellbeing",
            "description": "Soutien aux actions de la fondation",
        },
    }

    resp = requests.post(f"{BASE_URL}/payments", json=payload, headers=_headers(), timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "success":
        raise RuntimeError(f"Flutterwave error: {data}")
    link = data.get("data", {}).get("link")
    if not link:
        raise RuntimeError("No redirect link returned by Flutterwave")
    return link


def verify_transaction(transaction_id: str | int):
    resp = requests.get(f"{BASE_URL}/transactions/{transaction_id}/verify", headers=_headers(), timeout=20)
    resp.raise_for_status()
    return resp.json()

