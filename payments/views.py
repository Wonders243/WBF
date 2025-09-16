import json
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from .models import Payment
from .cinetpay import create_checkout, check_payment

@require_POST
@transaction.atomic
def donate_rdc_start(request):
    try:
        amount_cdf = int(request.POST.get("amount", "0"))
    except ValueError:
        return HttpResponseBadRequest("Montant invalide")

    if amount_cdf <= 0:
        return HttpResponseBadRequest("Montant requis")

    # Création en base d'une ligne PENDING
    user = request.user if request.user.is_authenticated else None
    tx_id, payload, cp_resp = create_checkout(amount_cdf, "Don  BAMU WELLBEING Foundation (RDC)", user or type("Anon", (), {})())

    p = Payment.objects.create(
        user=user,
        email=(getattr(user, "email", "") or request.POST.get("email", "")),
        phone_e164=request.POST.get("phone_e164", ""),
        name=(getattr(user, "get_full_name", lambda: "")() or request.POST.get("name", "")),
        provider=Payment.Provider.CINETPAY,
        provider_tx_id=tx_id,
        amount=payload["amount"],
        currency=payload["currency"],
        description=payload["description"],
        status=Payment.Status.PENDING,
        raw_request=payload,
        raw_response=cp_resp,
    )

    # CinetPay renvoie une URL de paiement
    payment_url = (cp_resp.get("data") or {}).get("payment_url")
    if not payment_url:
        p.status = Payment.Status.ERROR
        p.save(update_fields=["status"])
        messages.error(request, "Le prestataire de paiement est indisponible. Réessaie plus tard.")
        return redirect("core:don") if "core:don" in settings.ROOT_URLCONF else HttpResponseBadRequest("Erreur PSP")

    return HttpResponseRedirect(payment_url)

@require_GET
def cinetpay_return(request):
    """
    Page de retour (client). On relit le statut côté serveur pour afficher un message correct.
    """
    tx_id = request.GET.get("transaction_id") or request.GET.get("cpm_trans_id") or request.GET.get("token")
    if not tx_id:
        messages.info(request, "Merci pour votre paiement. Le traitement est en cours.")
        return redirect("payments:test")

    data = check_payment(tx_id)
    status = (data.get("data") or {}).get("status")
    try:
        p = Payment.objects.select_for_update().get(provider=Payment.Provider.CINETPAY, provider_tx_id=tx_id)
    except Payment.DoesNotExist:
        messages.warning(request, "Transaction inconnue (retour).")
        return redirect("payments:test")

    # Map statut
    if status == "ACCEPTED":
        p.status = Payment.Status.ACCEPTED
        messages.success(request, "Merci ! Votre don a bien été accepté.")
    elif status in {"REFUSED", "FAILED"}:
        p.status = Payment.Status.REFUSED
        messages.error(request, "Le paiement a été refusé.")
    elif status in {"CANCELED"}:
        p.status = Payment.Status.CANCELED
        messages.warning(request, "Le paiement a été annulé.")
    else:
        p.status = Payment.Status.PENDING
        messages.info(request, "Paiement en attente de confirmation.")

    p.raw_check = data
    p.provider_ref = (data.get("data") or {}).get("payment_token", "") or p.provider_ref
    p.save(update_fields=["status", "raw_check", "provider_ref"])
    return redirect("payments:test")

@csrf_exempt
def cinetpay_notify(request):
    """
    Webhook serveur-à-serveur: CinetPay appelle cette URL.
    On lit transaction_id et on confirme via /payment/check.
    Répondre 200 "ok" même si on n'a rien à faire (idempotence).
    """
    tx = request.POST.get("transaction_id") or request.GET.get("transaction_id")
    if not tx:
        return HttpResponse("ok", status=200)

    data = check_payment(tx)
    status = (data.get("data") or {}).get("status")

    # Idempotent update
    try:
        p = Payment.objects.select_for_update().get(provider=Payment.Provider.CINETPAY, provider_tx_id=tx)
    except Payment.DoesNotExist:
        # (Optionnel) créer un log annexe
        return HttpResponse("ok", status=200)

    old = p.status
    if status == "ACCEPTED":
        p.status = Payment.Status.ACCEPTED
    elif status in {"REFUSED", "FAILED"}:
        p.status = Payment.Status.REFUSED
    elif status in {"CANCELED"}:
        p.status = Payment.Status.CANCELED
    else:
        p.status = Payment.Status.PENDING

    p.raw_check = data
    p.provider_ref = (data.get("data") or {}).get("payment_token", "") or p.provider_ref
    if p.status != old:
        p.save(update_fields=["status", "raw_check", "provider_ref"])
        # TODO: déclencher email de reçu, envoi facture, etc.

    return HttpResponse("ok", status=200)

def donate_test(request):
    """
    Page simple pour tester: choisit un montant, poste sur /pay/rdc/start/.
    """
    return render(request, "payments/test.html", {})


def payment_maintenance(request):
    ctx = {
        "support_email": getattr(settings, "SUPPORT_EMAIL", ""),
        "support_phone": getattr(settings, "SUPPORT_PHONE", ""),
        "support_whatsapp": getattr(settings, "SUPPORT_WHATSAPP", ""),
        "support_url": getattr(settings, "SUPPORT_URL", ""),
    }
    # 503 = Service Unavailable (correct pour maintenance)
    return render(request, "payments/maintenance.html", ctx, status=503)
