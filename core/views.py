# core/views.py
from datetime import date

from django.contrib import messages
from django.db.models import Q
from django.forms import ModelForm, Textarea, NumberInput
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import DetailView, ListView
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from .forms import ContactForm
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from core.models import TeamMemberInvite
from core.forms import TeamMemberSelfForm
from .utils import grant_team_access
from staff.forms import VolunteerApplicationForm



from .models import (
    TeamMember,
    Partenaire,
    Project,
    Event,
    Testimonial,
    News,
    Donation,
    ContactMessage,
)

# -------------------------
# Forms (simples, inline)
# -------------------------
class ContactForm(ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "email", "subject", "message"]
        widgets = {"message": Textarea(attrs={"rows": 5})}


class DonationForm(ModelForm):
    class Meta:
        model = Donation
        fields = ["donor_name", "amount", "message"]
        widgets = {
            "amount": NumberInput(attrs={"step": "0.01", "min": "1"}),
            "message": Textarea(attrs={"rows": 4}),
        }


# -------------------------
# Pages publiques
# -------------------------
def accueil(request):
    projects = Project.objects.all()[:6]
    testimonials = Testimonial.objects.all()[:6]
    partners = Partenaire.objects.all()
    team = TeamMember.objects.all()[:6]
    upcoming_events = Event.objects.filter(date__gte=date.today()).order_by("date")[:6]
    news = News.objects.all()[:4]
    return render(
        request,
        "core/accueil.html",
        {
            "projects": projects,
            "testimonials": testimonials,
            "partners": partners,
            "team": team,
            "upcoming_events": upcoming_events,
            "news": news,
        },
    )

@login_required
def team_member_complete(request, token):
    invite = get_object_or_404(TeamMemberInvite, token=token)
    member = invite.member

    # Garde-fous
    if not invite.is_valid:
        messages.error(request, "Ce lien n'est plus valide.")
        return redirect("benevoles:dashboard")
    if not member.user_id or member.user_id != request.user.id:
        messages.error(request, "Ce lien appartient à un autre compte.")
        return redirect("benevoles:dashboard")

    if request.method == "POST":
        if (request.POST.get("action") or "").strip().lower() == "decline":
            invite.used_at = timezone.now()
            invite.save(update_fields=["used_at"])
            messages.info(request, "Vous avez décliné l'invitation. Merci pour votre réponse.")
            return redirect("benevoles:dashboard")
        form = TeamMemberSelfForm(request.POST, request.FILES, instance=member)
        if form.is_valid():
            obj = form.save()

            # Marquer l'invitation comme utilisée
            invite.used_at = timezone.now()
            invite.save(update_fields=["used_at"])

            # ⭐ Donner l'accès staff
            # Validation interne requise (pas d'activation automatique)

            messages.success(request, "Merci ! Votre fiche a été complétée ✅")
            # Rediriger directement dans l’espace staff
            return redirect("core:team_member_thanks")
        messages.error(request, "Veuillez corriger les erreurs.")
    else:
        form = TeamMemberSelfForm(instance=member)

    return render(request, "staff/team/complete_form.html", {
        "form": form,
        "member": member,
        "invite": invite,
    })

# -------------------------
# Projets
# -------------------------
class ProjectListView(ListView):
    model = Project
    template_name = "core/projects_list.html"
    context_object_name = "projects"
    paginate_by = 12

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
        return qs.order_by("title")



# -------------------------
# Evénements
# -------------------------
class EventListView(ListView):
    model = Event
    template_name = "core/events_list.html"
    context_object_name = "events"
    paginate_by = 12

    def get_queryset(self):
        qs = super().get_queryset()
        when = self.request.GET.get("when")
        if when == "past":
            qs = qs.filter(date__lt=date.today())
        elif when == "upcoming":
            qs = qs.filter(date__gte=date.today())
        return qs.order_by("-date")


class EventDetailView(DetailView):
    model = Event
    slug_field = "slug"
    slug_url_kwarg = "slug"
    template_name = "core/event_detail.html"
    context_object_name = "event"


# -------------------------
# News / Actus
# -------------------------
class NewsListView(ListView):
    model = News
    template_name = "core/news_list.html"
    context_object_name = "items"
    paginate_by = 12

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(content__icontains=q))
        return qs.order_by("-date")


class NewsDetailView(DetailView):
    model = News
    template_name = "core/news_detail.html"
    context_object_name = "item"


# -------------------------
# Contact
# -------------------------
def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Merci ! Votre message a bien été envoyé.")
            return redirect("core:contact")
        messages.error(request, "Veuillez corriger les erreurs du formulaire.")
    else:
        form = ContactForm()
    return render(request, "core/contact.html", {"form": form})


# -------------------------
# Dons
# -------------------------


def donation_success(request):
    return render(request, "core/donation_success.html")


from .forms import DonationForm
from .models import PaymentTransaction
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
import uuid

def _method_to_payment_options(method: str) -> str:
    mapping = {
        "card": "card",
        "mpesa": "mpesa",
        "mm_ghana": "mobilemoneyghana",
        "mm_uganda": "mobilemoneyuganda",
        "mm_zambia": "mobilemoneyzambia",
        "mm_franco": "mobilemoneyfranco",
        "bank_ng": "banktransfer",
        "ussd_ng": "ussd",
    }
    return mapping.get(method, "card")


def _is_currency_method_compatible(currency: str, method: str) -> bool:
    c = currency.upper()
    m = method
    if m == "mpesa":
        return c in {"KES", "TZS"}
    if m == "mm_ghana":
        return c == "GHS"
    if m == "mm_uganda":
        return c == "UGX"
    if m == "mm_zambia":
        return c == "ZMW"
    if m == "mm_franco":
        return c in {"XAF", "XOF"}
    if m in {"bank_ng", "ussd_ng"}:
        return c == "NGN"
    # card: widely supported among selected currencies
    return c in {"KES","TZS","UGX","GHS","ZMW","XAF","XOF","NGN","USD"}


def donation_create(request):
    """Démarre un paiement de don via Flutterwave (Mobile Money inclus)."""
    quick_amounts = [10, 20, 50, 100]
    if request.method == "POST":
        form = DonationForm(request.POST)
        currency = (request.POST.get("currency") or "USD").upper()
        method = (request.POST.get("method") or "card").strip()
        if form.is_valid():
            # Vérifier la configuration Flutterwave
            if not getattr(settings, "FLW_SECRET_KEY", ""):
                messages.error(request, "Paiement indisponible: configuration Flutterwave manquante (FLW_SECRET_KEY).")
                return render(request, "core/donation_form.html", {"form": form, "quick_amounts": quick_amounts})

            data = form.cleaned_data
            amount = data["amount"]
            donor_name = data.get("donor_name") or ""
            message = data.get("message") or ""

            # Mode RDC uniquement: restreindre à USD + carte (en attendant l’agrégateur RDC)
            if currency != "USD" or method != "card":
                messages.error(request, "Pour l’instant, seuls les paiements par carte en USD sont disponibles en RDC.")
                return render(request, "core/donation_form.html", {"form": form, "quick_amounts": quick_amounts})

            tx_ref = f"DON-{uuid.uuid4().hex[:12]}"
            return_url = request.build_absolute_uri(reverse("core:don_return"))

            p = PaymentTransaction.objects.create(
                provider="flutterwave",
                tx_ref=tx_ref,
                status=PaymentTransaction.Status.INITIATED,
                amount=amount,
                currency=currency,
                donor_name=donor_name,
                message=message,
                return_url=return_url,
            )

            try:
                from .payments.flutterwave import create_payment_link
                link = create_payment_link(
                    tx_ref=tx_ref,
                    amount=amount,
                    currency=currency,
                    redirect_url=return_url,
                    customer_name=donor_name,
                    customer_email=(request.user.email if getattr(request, "user", None) and request.user.is_authenticated else ""),
                    payment_options=_method_to_payment_options("card"),
                )
                return redirect(link)
            except Exception as e:
                messages.error(request, f"Paiement indisponible: {e}")
                p.status = PaymentTransaction.Status.FAILED
                p.save(update_fields=["status", "updated_at"])
                return redirect("core:don")
    else:
        form = DonationForm()
    return render(request, "core/donation_form.html", {"form": form, "quick_amounts": quick_amounts})
# -------------------------
# Candidature bénévolat (publique)
# -------------------------
def volunteer_apply(request):
    if request.method == "POST":
        form = VolunteerApplicationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Merci ! Votre candidature a bien été transmise.")
            return redirect("core:volunteer_apply")
        messages.error(request, "Veuillez corriger les erreurs du formulaire.")
    else:
        form = VolunteerApplicationForm()
    return render(request, "core/volunteer_apply.html", {"form": form})


def project_detail_legacy(request, pk):
    obj = get_object_or_404(Project, pk=pk)
    return redirect("core:project_detail", slug=obj.slug, permanent=True)

class ProjectDetailView(DetailView):
    model = Project
    slug_field = "slug"
    slug_url_kwarg = "slug"
    template_name = "core/project_detail.html"
    context_object_name = "project"


# -------------------------
# Paiements (Flutterwave)
# -------------------------
def don_return(request):
    status = (request.GET.get("status") or "").lower()
    tx_ref = request.GET.get("tx_ref") or ""
    tx_id = request.GET.get("transaction_id") or ""

    if not tx_ref:
        return HttpResponseBadRequest("Missing tx_ref")

    p = PaymentTransaction.objects.filter(tx_ref=tx_ref).first()
    if not p:
        return HttpResponseBadRequest("Unknown transaction")

    if status == "cancelled":
        p.status = PaymentTransaction.Status.CANCELLED
        p.save(update_fields=["status", "updated_at"])
        messages.info(request, "Paiement annulé.")
        return redirect("core:don")

    if not tx_id:
        messages.error(request, "Retour paiement invalide.")
        return redirect("core:don")

    try:
        from .payments.flutterwave import verify_transaction
        res = verify_transaction(tx_id)
        ok = res.get("status") == "success" and res.get("data", {}).get("status") == "successful"
        amount_ok = str(res.get("data", {}).get("amount")) == str(p.amount)
        currency_ok = (res.get("data", {}).get("currency") or "").upper() == p.currency.upper()
        if ok and amount_ok and currency_ok:
            if not p.donation_id:
                d = Donation.objects.create(donor_name=p.donor_name or None, amount=p.amount, message=p.message or None)
                p.donation = d
            p.provider_tx_id = str(res.get("data", {}).get("id"))
            p.status = PaymentTransaction.Status.SUCCESS
            p.save(update_fields=["provider_tx_id", "status", "donation", "updated_at"])
            return redirect("core:don_success")
        else:
            p.status = PaymentTransaction.Status.FAILED
            p.save(update_fields=["status", "updated_at"])
            messages.error(request, "Le paiement n’a pas été validé.")
            return redirect("core:don")
    except Exception as e:
        messages.error(request, f"Vérification impossible: {e}")
        return redirect("core:don")


@csrf_exempt
def flutterwave_webhook(request):
    expected = getattr(settings, "FLW_WEBHOOK_SECRET", "")
    got = request.headers.get("verif-hash") or request.META.get("HTTP_VERIF_HASH", "")
    if not expected or got != expected:
        return HttpResponseForbidden("Invalid signature")

    try:
        import json
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid payload")

    data = payload.get("data", {})
    tx_ref = data.get("tx_ref") or data.get("txRef")
    status = (data.get("status") or "").lower()
    tx_id = data.get("id")

    if not tx_ref:
        return HttpResponse("ok")

    p = PaymentTransaction.objects.filter(tx_ref=tx_ref).first()
    if not p:
        return HttpResponse("ok")

    p.webhook_seen = True
    if status == "successful":
        try:
            from .payments.flutterwave import verify_transaction
            res = verify_transaction(tx_id)
            ok = res.get("status") == "success" and res.get("data", {}).get("status") == "successful"
            if ok and not p.donation_id:
                d = Donation.objects.create(donor_name=p.donor_name or None, amount=p.amount, message=p.message or None)
                p.donation = d
            p.provider_tx_id = str(tx_id)
            p.status = PaymentTransaction.Status.SUCCESS
        except Exception:
            p.status = PaymentTransaction.Status.PENDING
    elif status in {"failed", "cancelled"}:
        p.status = PaymentTransaction.Status.FAILED if status == "failed" else PaymentTransaction.Status.CANCELLED
    p.save()
    return HttpResponse("ok")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["other_projects"] = (
            Project.objects.exclude(pk=self.object.pk).order_by("-id")[:3]
        )
        return ctx


def event_detail_legacy(request, pk):
    obj = get_object_or_404(Event, pk=pk)
    return redirect("core:event_detail", slug=obj.slug, permanent=True)





def nous(request):
    team = TeamMember.objects.all()
    partners = Partenaire.objects.all()
    testimonials = Testimonial.objects.all()[:10]
    form = ContactForm()  # pour afficher le form sur la page "nous"
    return render(request, "core/nous.html", {
        "team": team, "partners": partners, "testimonials": testimonials, "form": form
    })


def contact(request):
    """
    Traite le POST du formulaire de contact.
    - Sauvegarde en base (ContactMessage)
    - Envoie un email de notification
    - Redirige avec message de succès
    """
    if request.method != "POST":
        # Si tu as une page contact dédiée, on peut l'afficher ici.
        return redirect("core:nous")

    form = ContactForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Veuillez corriger les erreurs du formulaire.")
        # On ré-affiche la page 'nous' avec les erreurs
        team = TeamMember.objects.all()
        partners = Partenaire.objects.all()
        testimonials = Testimonial.objects.all()[:10]
        return render(request, "core/nous.html", {
            "team": team, "partners": partners, "testimonials": testimonials, "form": form
        })

    # 1) Sauvegarde en BDD
    msg_obj = form.save()  # crée bien une ligne dans la table core_contactmessage

    # 2) Envoi d'email (notification interne)
    try:
        to_email = getattr(settings, "CONTACT_EMAIL", None) or getattr(settings, "DEFAULT_FROM_EMAIL", None)
        if to_email:
            subject = f"[Contact] {msg_obj.subject}"
            body = render_to_string("emails/contact_notification.txt", {"m": msg_obj})
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                to=[to_email],
                reply_to=[msg_obj.email] if msg_obj.email else None,
            )
            email.send(fail_silently=True)
    except Exception:
        # On n'interrompt pas l'expérience si l'envoi mail échoue
        pass

    messages.success(request, "Merci ! Votre message a bien été envoyé.")
    return redirect("core:nous")


def coming_soon(request):
    ctx = {
        "eta": "septembre 2025",              # optionnel
        "subtext": "Des mises à jour régulières arrivent d’ici là.",
        "back_url": "/",                      # optionnel
        "contact_url": "/contact/",           # optionnel
        # "launch_at": "2025-09-15T10:00:00Z" # optionnel (active le compte à rebours)
    }
    # 503 = Service Unavailable (temporaire)
    return render(request, "coming_soon.html", ctx, status=503)
