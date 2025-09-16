import os, uuid, requests

CINET_API = "https://api-checkout.cinetpay.com/v2/payment"
CINET_CHECK = "https://api-checkout.cinetpay.com/v2/payment/check"

def _env(name, default=""):
    v = os.getenv(name, default)
    if v is None:
        return default
    return v

def round_cdf_to_5(amount_cdf: int) -> int:
    """CinetPay CDF: montant multiple de 5 recommandé."""
    amount_cdf = int(amount_cdf)
    r = amount_cdf % 5
    return amount_cdf if r == 0 else amount_cdf + (5 - r)

def create_checkout(amount_cdf: int, description: str, customer) -> tuple[str, dict]:
    tx_id = uuid.uuid4().hex  # unique côté marchand
    payload = {
        "apikey":   _env("CINETPAY_APIKEY"),
        "site_id":  _env("CINETPAY_SITE_ID"),
        "transaction_id": tx_id,
        "amount":   round_cdf_to_5(amount_cdf),
        "currency": _env("CINETPAY_CURRENCY", "CDF"),
        "description": description[:200],
        "return_url": _env("CINETPAY_RETURN_URL"),
        "notify_url": _env("CINETPAY_NOTIFY_URL"),
        "channels": "MOBILE_MONEY",
        "lang": "FR",
        "customer_id": getattr(customer, "pk", None) or "anonymous",
        "customer_name": getattr(customer, "first_name", "") or "Donateur",
        "customer_surname": getattr(customer, "last_name", "") or "RDC",
        "customer_phone_number": getattr(customer, "phone_e164", "") or "",
        "customer_email": getattr(customer, "email", "") or "",
        "customer_country": "CD",
    }
    r = requests.post(CINET_API, json=payload, timeout=35)
    r.raise_for_status()
    data = r.json()
    return tx_id, payload, data

def check_payment(tx_id: str) -> dict:
    payload = {
        "apikey": _env("CINETPAY_APIKEY"),
        "site_id": _env("CINETPAY_SITE_ID"),
        "transaction_id": tx_id,
    }
    r = requests.post(CINET_CHECK, json=payload, timeout=35)
    r.raise_for_status()
    return r.json()
