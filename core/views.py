# core/views.py
from datetime import date

from django.contrib import messages
from django.db.models import Q
from django.forms import ModelForm, Textarea
from django.shortcuts import get_object_or_404, redirect, render
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



def donation_create(request):
    """Affiche une page statique le temps de sélectionner un prestataire de paiement."""
    context = {
        "support_email": getattr(settings, "SUPPORT_EMAIL", ""),
        "support_phone": getattr(settings, "SUPPORT_PHONE", ""),
        "support_whatsapp": getattr(settings, "SUPPORT_WHATSAPP", ""),
    }
    return render(request, "core/donation_form.html", context)



def donation_success(request):
    return render(request, "core/donation_success.html")



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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["other_projects"] = Project.objects.exclude(pk=self.object.pk).order_by("-id")[:3]
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
