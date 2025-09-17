# staff/views.py
import os
from django.contrib import messages 
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db.models import Q, Sum,Count
from core.models import Event, Project, TeamMember, Partenaire,TeamMemberInvite
from core.models import News, Testimonial, EducationStory, EducationStoryImage
from .models import Mission, MissionSignup
from datetime import datetime, timedelta, date as ddate
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect,render
from accounts.models import Availability
from .forms import InviteFilterForm, BulkInviteForm, EventForm, MissionForm, ProjectForm
from .forms import NewsForm, TestimonialForm, EducationStoryForm
from django.db import transaction, IntegrityError
from django.shortcuts import resolve_url
from django.views.generic import ListView, DetailView
from .forms import TeamMemberForm, PartenaireForm
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.mail import send_mail
from .models import VolunteerApplication, VolunteerApplicationDocument
from .forms import VolunteerApplicationForm, DocumentFormSet
from django.db.models import Count
from django.urls import reverse
from decimal import Decimal
from django.views.decorators.cache import never_cache
from django.forms import inlineformset_factory

# Modèles — adapte ces imports à ton projet
from staff.models import MissionSignup  # ← déjà utilisé dans ton code
# from staff.models import Mission  # si Mission est dans staff
# from core.models import Mission   # sinon, adapte
# from events.models import Event   # si tu l’utilises ici
# from core.models import UserDocument, HoursEntry  # adapte si ailleurs
# from accounts.models import Volunteer  # pour top bénévoles si besoin



# staff/views.py — AJOUTER cette vue
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.urls import reverse

from django.conf import settings

from staff.security.services import require_auth_key
from staff.security.models import AuthorizationKey, AuthorizationKeyUse


User = get_user_model()


from .security.services import require_auth_key
from .security.models import AuthorizationKey




from accounts.models import (
    Volunteer, UserDocument, HoursEntry, HoursEntryProof,
    VolunteerSkill, Availability,
)

@staff_member_required
@require_auth_key(
    action="team.invite",
    level=AuthorizationKey.Level.MEDIUM,
    superuser_bypass=True,
)
def staff_team_send_invite(request, slug):
    member = get_object_or_404(TeamMember, slug=slug)
    if not member.user or not member.user.email:
        messages.error(request, "Aucun compte utilisateur ou email pour ce membre.")
        return redirect("staff:team_detail", slug=slug)

    invite = TeamMemberInvite.objects.create(member=member, created_by=request.user)

    try:
        url = request.build_absolute_uri(reverse("team_complete", args=[invite.token]))
    except Exception:
        url = request.build_absolute_uri(f"/team/complete/{invite.token}/")

    context = {
        "member": member,
        "invite": invite,
        "url": url,
        "expires_at": invite.expires_at,
    }

    subject = f"Complétez votre fiche membre — {getattr(settings, 'SITE_NAME', 'Notre site')}"
    body_txt = render_to_string("emails/team_member_invite.txt", context)
    body_html = render_to_string("emails/team_member_invite.html", context)

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or "ne_pas_repondre@bamuwellbeing.org"
    send_mail(subject, body_txt, from_email, [member.user.email], html_message=body_html)

    messages.success(request, f"Invitation envoyée à {member.user.email} ✅")
    return redirect("staff:team_detail", slug=slug)

# --------- Helpers ---------
def _parse_date(s: str):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None

def _mission_date(m: Mission):
    # priorité à l'event.date, sinon start_date
    return (getattr(getattr(m, "event", None), "date", None)
            or getattr(m, "start_date", None))

def _paginate(request, items, per_page=12):
    paginator = Paginator(items, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    return page_obj


def _safe_redirect(request):
    return (
        request.POST.get("next")
        or request.GET.get("next")
        or request.META.get("HTTP_REFERER")
        or resolve_url("benevoles:missions_browse")
    )
# --------- PROJETS (Staff) ---------

@staff_member_required
def projects_list(request):
    q        = (request.GET.get("q") or "").strip()
    partner  = (request.GET.get("partner") or "").strip()
    has_link = (request.GET.get("has_link") or "").strip()  # "yes" / "" (tous)

    qs = (Project.objects
          .prefetch_related("partners", "events")
          .annotate(
              events_count=Count("events", distinct=True),
              missions_count=Count("events__missions", distinct=True),  # Mission.event.related_name="missions"
          ))

    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if partner.isdigit():
        qs = qs.filter(partners__id=int(partner))
    if has_link == "yes":
        qs = qs.exclude(link__isnull=True).exclude(link__exact="")

    page_obj = Paginator(qs.order_by("title", "id"), 15).get_page(request.GET.get("page"))

    # pour le select partenaires
    from core.models import Partenaire  # adapte l'import si besoin
    partners = Partenaire.objects.order_by("name" if hasattr(Partenaire, "name") else "title")

    rows = []
    for p in page_obj.object_list:
        labels = []
        for x in p.partners.all():
            labels.append(getattr(x, "name", None) or getattr(x, "title", None) or str(x))
        rows.append({
            "id": p.id,
            "title": p.title,
            "partners": ", ".join(labels) or "—",
            "events_count": getattr(p, "events_count", 0),
            "missions_count": getattr(p, "missions_count", 0),
            "link": p.link or "",
        })

    preserved = request.GET.copy()
    preserved.pop("page", None)
    qs_str = preserved.urlencode()

    return render(request, "staff/projects_list.html", {
        "rows": rows,
        "page_obj": page_obj,
        "partners": partners,
        "qs": qs_str,
    })

@staff_member_required
def profil_staff(request):
    user = request.user
    # Clés API créées par l'utilisateur
    keys_qs = AuthorizationKey.objects.filter(created_by=user).order_by("-created_at")
    keys = list(keys_qs[:5])
    keys_total = keys_qs.count()

    # Utilisations récentes de clés par l'utilisateur
    uses = list(
        AuthorizationKeyUse.objects.select_related("key")
        .filter(used_by=user)
        .order_by("-used_at")[:5]
    )

    # Lien éventuel avec la fiche équipe
    team_member = getattr(user, "team_member", None)

    return render(request, "staff/profil_staff.html", {
        "user": user,
        "team_member": team_member,
        "api_keys": keys,
        "api_keys_total": keys_total,
        "key_uses": uses,
    })


# --------- PROJET (Staff) ---------

@staff_member_required
def project_detail(request, pk):
    project = get_object_or_404(Project.objects.prefetch_related("partners", "events__missions"), pk=pk)

    partners = list(project.partners.all())
    events   = list(project.events.order_by("-date", "-id"))
    # missions via les events du projet
    missions = []
    for e in events:
        for m in e.missions.all():
            missions.append(m)

    return render(request, "staff/project_detail.html", {
        "project": project,
        "partners": partners,
        "events": events,
        "missions": missions,
    })


@staff_member_required
@require_auth_key(
    action="project.create",
    level=AuthorizationKey.Level.HIGH,
    superuser_bypass=True,
    return_403=True,
    methods=("POST",),   # clé exigée UNIQUEMENT à l’envoi
)
def project_create(request):
    if request.method == "POST":
        form = ProjectForm(request.POST, request.FILES)
        if form.is_valid():
            p = form.save()
            messages.success(request, "Projet créé.")
            return redirect("staff:project_detail", pk=p.pk)
    else:
        form = ProjectForm()
    return render(request, "staff/project_form.html", {"form": form})


@staff_member_required
@require_auth_key(
    action="project.update",
    level=AuthorizationKey.Level.HIGH,
    superuser_bypass=True,
    return_403=True,
    methods=("POST",),
)
def project_update(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if request.method == "POST":
        form = ProjectForm(request.POST, request.FILES, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, "Projet mis à jour.")
            return redirect("staff:project_detail", pk=project.pk)
    else:
        form = ProjectForm(instance=project)
    return render(request, "staff/project_form.html", {"form": form, "project": project})




# --------- MISSIONS ---------

ACTIVE_STATUSES = {
    MissionSignup.Status.INVITED,
    MissionSignup.Status.PENDING,
    MissionSignup.Status.ACCEPTED,
}
from datetime import date as _date, datetime


def _as_local_date(v):
    """Normalise un champ date/datetime en date locale (ou None)."""
    if v is None:
        return None
    if isinstance(v, datetime):
        try:
            v = timezone.localtime(v)
        except Exception:
            # si v est naïf, on le garde tel quel mais on extrait la date
            pass
        return v.date()
    # déjà une date
    return v

@staff_member_required
def missions_list(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    dfrom = _parse_date(request.GET.get("from"))  # -> date ou None
    dto   = _parse_date(request.GET.get("to"))    # -> date ou None

    qs = Mission.objects.select_related("event").all()
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(location__icontains=q) |
            Q(event__title__icontains=q)
        )

    rows = []
    for m in qs:
        d_raw = _mission_date(m)           # peut être date OU datetime selon ton modèle
        d = _as_local_date(d_raw)          # <- on normalise en date

        # Filtres : tout en date
        if dfrom and d and d < dfrom:
            continue
        if dto and d and d > dto:
            continue

        rows.append({
            "id": m.id,
            "title": m.title,
            "event_title": getattr(m.event, "title", None),
            "date": d,                     # on stocke la date normalisée
            "capacity": m.capacity,
            "status": m.status,
        })

    # Tri : tout en date (évite le mix date/datetime)
    rows.sort(key=lambda r: (r["date"] or _date.max, r["id"]))

    page_obj = _paginate(request, rows, per_page=12)
    return render(request, "staff/missions_list.html", {"page_obj": page_obj})

@staff_member_required
@require_auth_key(
    action="mission.create",
    level=AuthorizationKey.Level.HIGH,
    superuser_bypass=True,   # le superuser n’a pas besoin de clé
)
def mission_create(request):
    initial = {}
    event_id = request.GET.get("event")
    if event_id and event_id.isdigit():
        initial["event"] = int(event_id)

    if request.method == "POST":
        form = MissionForm(request.POST)
        if form.is_valid():
            m = form.save()
            messages.success(request, "Mission créée.")
            return redirect("staff:mission_detail", pk=m.pk)
    else:
        form = MissionForm(initial=initial)
    return render(request, "staff/mission_form.html", {"form": form})


@staff_member_required
@require_auth_key(
    action="mission.update",
    level=AuthorizationKey.Level.HIGH,
    superuser_bypass=True,   # le superuser n’a pas besoin de clé
)
def mission_update(request, pk):
    mission = get_object_or_404(Mission, pk=pk)
    if request.method == "POST":
        form = MissionForm(request.POST, instance=mission)
        if form.is_valid():
            form.save()
            messages.success(request, "Mission mise à jour.")
            return redirect("staff:mission_detail", pk=mission.pk)
    else:
        form = MissionForm(instance=mission)
    return render(request, "staff/mission_form.html", {"form": form})


@staff_member_required
def mission_detail_alias(request, mission_id):
    # redirige proprement vers l’URL canonique qui attend pk
    return redirect("staff:mission_detail", pk=mission_id)

@staff_member_required
def mission_detail(request, pk):
    mission = get_object_or_404(Mission.objects.select_related("event"), pk=pk)

    # Stats d'inscriptions
    qs = (MissionSignup.objects
          .filter(mission=mission)
          .select_related("volunteer__user")
          .order_by("-id"))
    counts = {
        "total": qs.count(),
        "accepted": qs.filter(status=MissionSignup.Status.ACCEPTED).count(),
        "pending": qs.filter(status=MissionSignup.Status.PENDING).count(),
    }

    # Groupes par statut pour l'UI
    def map_item(s):
        return {"id": s.id, "volunteer_name": s.volunteer.display_name, "created_at": s.created_at}

    signups_by_status = [
        {"key": "pending", "label": "En attente", "items": [map_item(s) for s in qs if s.status == MissionSignup.Status.PENDING]},
        {"key": "invited", "label": "Invités",     "items": [map_item(s) for s in qs if s.status == MissionSignup.Status.INVITED]},
        {"key": "accepted","label": "Acceptés",    "items": [map_item(s) for s in qs if s.status == MissionSignup.Status.ACCEPTED]},
        {"key": "declined","label": "Refusés",     "items": [map_item(s) for s in qs if s.status == MissionSignup.Status.DECLINED]},
        {"key": "cancelled","label": "Annulés",    "items": [map_item(s) for s in qs if s.status == MissionSignup.Status.CANCELLED]},
    ]

    return render(request, "staff/mission_detail.html", {
        "mission": mission,
        "counts": counts,
        "signups_by_status": signups_by_status,
    })

# --------- invitation aux missions ---------

@staff_member_required
def mission_invite_view(request, mission_id):
    mission = get_object_or_404(Mission, pk=mission_id)

    already_ids = MissionSignup.objects.filter(mission=mission).values_list("volunteer_id", flat=True)
    qs = Volunteer.objects.filter().exclude(id__in=already_ids)

    # ---- Filtre ville identique ----
    if mission.city_id:
        qs = qs.filter(city_id=mission.city_id)
    # --------------------------------

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(user__username__icontains=q) | Q(user__email__icontains=q))

    volunteers = qs.select_related("user", "city").order_by("name", "user__username")

    if request.method == "POST":
        selected_ids = request.POST.getlist("volunteer_ids")
        created = 0
        for vid in selected_ids:
            obj, is_new = MissionSignup.objects.get_or_create(
                mission=mission, volunteer_id=vid, defaults={"status": MissionSignup.Status.INVITED}
            )
            if is_new:
                created += 1
        messages.success(request, f"{created} invitation(s) envoyée(s).")
        return redirect("staff:mission_detail", mission_id=mission.id)

    return render(request, "staff/mission_invite.html", {"mission": mission, "volunteers": volunteers, "q": q})


@staff_member_required
@require_auth_key(
    action="mission.invite",
    level=AuthorizationKey.Level.LOW,
    superuser_bypass=True,
    return_403=True,
    methods=("POST",),
)
def mission_invite(request, mission_id):
    mission = get_object_or_404(Mission.objects.select_related("event"), pk=mission_id)

    # ---------- Filtres ----------
    f = InviteFilterForm(request.GET or None)
    qs = Volunteer.objects.select_related("user").all()

    if f.is_valid():
        q     = f.cleaned_data.get("q") or ""
        skill = f.cleaned_data.get("skill") or ""
        day   = f.cleaned_data.get("day") or ""
        slot  = f.cleaned_data.get("slot") or ""
        only_available = bool(f.cleaned_data.get("only_available"))

        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(email__icontains=q) |
                Q(phone__icontains=q) |
                Q(user__username__icontains=q) |
                Q(user__first_name__icontains=q) |
                Q(user__last_name__icontains=q)
            )

        if skill:
            vs = VolunteerSkill.objects.select_related("skill")\
                                       .filter(skill__name__icontains=skill)
            qs = qs.filter(id__in=vs.values_list("volunteer_id", flat=True))

        if day:
            qs = qs.filter(
                id__in=Availability.objects.filter(day=day)
                                           .values_list("volunteer_id", flat=True)
            )
        if slot:
            qs = qs.filter(
                id__in=Availability.objects.filter(slot=slot)
                                           .values_list("volunteer_id", flat=True)
            )
    else:
        # défaut raisonnable si filtre invalide
        only_available = True

    # ---------- Statuts existants pour CETTE mission ----------
    vol_ids = list(qs.values_list("id", flat=True))
    status_map = {
        v_id: status
        for (v_id, status) in MissionSignup.objects.filter(
            mission_id=mission.id, volunteer_id__in=vol_ids
        ).values_list("volunteer_id", "status")
    }

    ACTIVE_STATUSES = {
        MissionSignup.Status.INVITED,
        MissionSignup.Status.PENDING,
        MissionSignup.Status.ACCEPTED,
    }

    # Masquer déjà invités/en cours/acceptés si demandé
    if f.is_valid() and only_available:
        masked_ids = [vid for vid, st in status_map.items() if st in ACTIVE_STATUSES]
        if masked_ids:
            qs = qs.exclude(id__in=masked_ids)

    # ---------- Prefetch compétences / dispos ----------
    skills_by_vol = {}
    for vs in (VolunteerSkill.objects.select_related("skill")
               .filter(volunteer_id__in=qs.values_list("id", flat=True))):
        skills_by_vol.setdefault(vs.volunteer_id, []).append(vs.skill.name)

    avail_by_vol = {}
    for av in Availability.objects.filter(volunteer_id__in=qs.values_list("id", flat=True)):
        avail_by_vol.setdefault(av.volunteer_id, []).append(f"{av.day} {av.slot}".strip())

    # ---------- Pagination ----------
    paginator = Paginator(qs.order_by("name", "user__username"), 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    # ---------- POST (envoi d'invitations) ----------
    if request.method == "POST":
        post_ids = request.POST.getlist("volunteer_ids")
        note = (request.POST.get("note") or "").strip()

        if not post_ids:
            messages.warning(request, "Sélectionnez au moins un bénévole.")
            # On reste sur la même page/qs
            return redirect(f"{request.path}?{request.GET.urlencode()}")

        # sécuriser : restreindre aux bénévoles visibles sur la page courante
        page_ids = list(page_obj.object_list.values_list("id", flat=True))
        target_ids = [int(x) for x in post_ids if x.isdigit() and int(x) in page_ids]

        if not target_ids:
            messages.warning(request, "La sélection ne correspond pas à la page affichée.")
            return redirect(f"{request.path}?{request.GET.urlencode()}")

        created, updated, skipped = 0, 0, 0
        now = timezone.now()

        for vid in target_ids:
            # On récupère une éventuelle inscription existante (évite les doublons)
            signup = MissionSignup.objects.filter(
                mission=mission, volunteer_id=vid
            ).order_by('-id').first()

            if signup is None:
                # Créer une nouvelle invitation
                signup = MissionSignup(
                    mission=mission,
                    volunteer_id=vid,
                    status=MissionSignup.Status.INVITED,
                    invited_by=request.user,
                    note=note[:255] if note else "",
                )
                signup.save()
                created += 1
            else:
                # Déjà présent : réactiver si annulé/refusé, sinon ignorer
                if signup.status in {MissionSignup.Status.DECLINED, MissionSignup.Status.CANCELLED}:
                    signup.status = MissionSignup.Status.INVITED
                    signup.invited_by = request.user
                    if note:
                        signup.note = note[:255]
                    signup.responded_at = None
                    signup.save(update_fields=["status", "invited_by", "note", "responded_at"])
                    updated += 1
                else:
                    skipped += 1

        parts = []
        if created: parts.append(f"{created} invitation(s) envoyée(s)")
        if updated: parts.append(f"{updated} réactivée(s)")
        if skipped: parts.append(f"{skipped} ignorée(s) (déjà invitées/en cours/acceptées)")
        messages.success(request, " ; ".join(parts) if parts else "Aucune invitation envoyée.")

        # Après POST, on désactive le filtre only_available pour VOIR les invités ré-apparaitre
        params = request.GET.copy()
        params['only_available'] = '0'
        params['page'] = '1'
        return redirect(f"{request.path}?{params.urlencode()}")

    # ---------- Préparer le BulkInviteForm (IDs de la page courante) ----------
    bulk_form = BulkInviteForm()
    bulk_form.fields["volunteer_ids"].choices = [(str(v.id), str(v.id)) for v in page_obj.object_list]

    return render(request, "staff/mission_invite.html", {
        "mission": mission,
        "filter_form": f,
        "bulk_form": bulk_form,
        "page_obj": page_obj,
        "status_map": status_map,
        "skills_by_vol": skills_by_vol,
        "avail_by_vol": avail_by_vol,
        "only_available": only_available,  # pour le checked fiable dans le template
    })


# --------- INSCRIPTIONS (actions bénévole) ---------
def _safe_redirect(request, default="benevoles:dashboard"):
    """
    Essaie de revenir à la page précédente, sinon vers un fallback nommé.
    """
    return request.META.get("HTTP_REFERER") or reverse(default)


@login_required
@require_POST
def mission_accept(request, signup_id):
    """
    Le bénévole accepte une invitation OU une candidature en attente.
    - Autorisé : INVITED, PENDING
    - Bloqué : autres statuts (ACCEPTED, DECLINED, CANCELLED, etc.)
    - Respecte la capacité s'il y en a une.
    """
    with transaction.atomic():
        # Verrouille la ligne de signup + récupère la mission
        s = (MissionSignup.objects
             .select_for_update()
             .select_related("mission")
             .get(pk=signup_id, volunteer__user=request.user))

        # Refuse les transitions non valides
        allowed = {MissionSignup.Status.INVITED, MissionSignup.Status.PENDING}
        if s.status not in allowed:
            messages.info(
                request,
                f"Impossible d’accepter : statut actuel = « {s.get_status_display()} »."
            )
            return redirect(_safe_redirect(request))

        m = (Mission.objects
             .select_for_update()
             .only("id", "capacity", "start_date")
             .get(pk=s.mission_id))

        # Optionnel : empêcher l'acceptation si la mission est déjà passée
        if getattr(m, "start_date", None):
            now = timezone.now()
            try:
                # si start_date est naïve, on compare quand même prudemment
                if m.start_date <= now:
                    messages.warning(request, "Cette mission a déjà commencé/est passée.")
                    return redirect(_safe_redirect(request))
            except TypeError:
                pass  # ignore si aware/naive mismatch, ou supprime ce bloc si inutile

        # Capacité : si définie (>0), ne pas dépasser
        cap = int(m.capacity or 0)
        if cap > 0:
            # Compte sous verrou les ACCEPTED pour cette mission
            accepted_count = (MissionSignup.objects
                              .select_for_update()
                              .filter(mission_id=m.id, status=MissionSignup.Status.ACCEPTED)
                              .count())
            if accepted_count >= cap:
                messages.warning(request, "Désolé, il n’y a plus de places disponibles sur cette mission.")
                return redirect(_safe_redirect(request))

        # Transition → ACCEPTED
        s.status = MissionSignup.Status.ACCEPTED
        s.responded_at = timezone.now()
        s.save(update_fields=["status", "responded_at"])

    messages.success(request, "Mission acceptée ✅")
    return redirect(_safe_redirect(request))

@login_required
@require_POST
def mission_cancel(request, signup_id):
    # On cible l’inscription précise + on vérifie qu’elle appartient bien à l’utilisateur connecté
    s = get_object_or_404(
        MissionSignup.objects.select_related("mission", "volunteer__user"),
        pk=signup_id,
        volunteer__user=request.user,
    )

    actifs = {MissionSignup.Status.PENDING, MissionSignup.Status.INVITED, MissionSignup.Status.ACCEPTED}
    if s.status in actifs:
        s.status = MissionSignup.Status.CANCELLED
        if hasattr(s, "responded_at"):
            s.responded_at = timezone.now()
            s.save(update_fields=["status", "responded_at"])
        else:
            s.save(update_fields=["status"])
        messages.success(request, f"Candidature pour « {s.mission.title} » annulée.")
    else:
        messages.info(request, "Cette candidature n’est pas active, rien à annuler.")
    return redirect(_safe_redirect(request))

@login_required
@require_POST
def mission_decline(request, signup_id):
    s = get_object_or_404(MissionSignup, pk=signup_id, volunteer__user=request.user)
    if s.status == MissionSignup.Status.INVITED:
        s.status = MissionSignup.Status.DECLINED
        msg = "Invitation refusée."
    elif s.status in {MissionSignup.Status.PENDING, MissionSignup.Status.ACCEPTED}:
        s.status = MissionSignup.Status.CANCELLED
        msg = "Candidature annulée."
    else:
        messages.info(request, "Cette candidature n’est pas active, rien à faire.")
        return redirect(_safe_redirect(request))
    s.responded_at = timezone.now()
    s.save(update_fields=["status","responded_at"])
    messages.info(request, msg)
    return redirect(_safe_redirect(request))

@login_required
@require_POST
def mission_apply(request, mission_id):
    """Le bénévole se porte candidat (status: pending) sur une mission publiée."""
    mission = get_object_or_404(Mission, pk=mission_id, status="published")

    # (optionnel) bloquer les missions passées
    if mission.end_date and mission.end_date < timezone.now():
        messages.error(request, "Cette mission est déjà passée.")
        return redirect(_safe_redirect(request))

    # 👉 ici : on récupère simplement le bénévole lié à l'utilisateur courant
    volunteer = get_object_or_404(Volunteer, user=request.user)

    try:
        with transaction.atomic():
            signup, created = MissionSignup.objects.get_or_create(
                mission=mission,
                volunteer=volunteer,
                defaults={"status": MissionSignup.Status.PENDING},
            )

            if created:
                messages.success(request, "Votre candidature a été envoyée. Le staff vous confirmera.")
            else:
                if signup.status in {MissionSignup.Status.CANCELLED, MissionSignup.Status.DECLINED}:
                    signup.status = MissionSignup.Status.PENDING
                    if hasattr(signup, "responded_at"):
                        signup.responded_at = None
                        signup.save(update_fields=["status", "responded_at"])
                    else:
                        signup.save(update_fields=["status"])
                    messages.success(request, "Votre candidature a été renvoyée.")
                elif signup.status in {MissionSignup.Status.PENDING, MissionSignup.Status.INVITED, MissionSignup.Status.ACCEPTED}:
                    messages.info(request, "Vous avez déjà une demande en cours pour cette mission.")
                else:
                    messages.info(request, "Votre situation actuelle ne permet pas de recandidater.")
    except IntegrityError:
        messages.info(request, "Vous avez déjà une demande pour cette mission.")

    return redirect(_safe_redirect(request))

# Annulation d’une invitation (STAFF)
@login_required
@user_passes_test(lambda u: u.is_staff)
@require_POST
@require_auth_key(
    action="invite.cancel",
    level=AuthorizationKey.Level.LOW,
    superuser_bypass=True,
    return_403=True,
    methods=("POST",),
)
def mission_cancel_invite(request, signup_id: int):
    """
    Annule une invitation envoyée par le staff (statut INVITED -> CANCELLED).
    Ne traite pas les candidatures des bénévoles (PENDING), ni les autres statuts.
    """
    s = get_object_or_404(MissionSignup, pk=signup_id)

    if s.status != MissionSignup.Status.INVITED:
        messages.info(request, "Cette inscription n’est pas une invitation active.")
        return redirect(_redirect_to_signup_parent(request, s))

    s.status = MissionSignup.Status.CANCELLED
    s.responded_at = timezone.now()
    s.save(update_fields=["status", "responded_at"])

    messages.success(request, "Invitation annulée.")
    return redirect(_redirect_to_signup_parent(request, s))


# --------- DASHBOARD ---------

# Helpers sûrs ( évite les AttributeError quand certains champs n'existent pas )
def _get(obj, name, default=None):
    try:
        v = getattr(obj, name)
        return v if v not in (None, "") else default
    except Exception:
        return default

def _to_date(value):
    if not value:
        return None
    if hasattr(value, "date"):
        return value.date()
    if isinstance(value, ddate):
        return value
    return None


# Optionnels / tolérants
try:
    from notifications.models import Notification
except Exception:
    Notification = None

try:
    from payments.models import Payment
except Exception:
    Payment = None


@staff_member_required
def staff_dashboard(request):
    """Super dashboard staff : KPIs + listes + raccourcis, basé sur tes modèles/URLs existants."""
    today = timezone.localdate()
    start_month = today.replace(day=1)
    start_30 = today - timedelta(days=29)
    seven_days_ago = today - timedelta(days=7)

    # -------- KPIs (solides + quelques ajouts) --------
    events_upcoming = Event.objects.filter(date__gte=today).count()
    projects_total = Project.objects.count()
    volunteers_total = Volunteer.objects.count()

    hours_7d_sum = (HoursEntry.objects
                    .filter(date__gte=seven_days_ago)
                    .aggregate(total=Sum("hours"))["total"] or 0)

    docs_total = UserDocument.objects.count()
    docs_pending_review = (
        UserDocument.objects.filter(status__in=["submitted", "under_review"]).count()
        if hasattr(UserDocument, "status") else 0
    )

    applications_pending = 0
    try:
        from staff.models import VolunteerApplication, ApplicationStatus
        applications_pending = VolunteerApplication.objects.filter(status=ApplicationStatus.PENDING).count()
    except Exception:
        pass

    payments_7d_count = payments_7d_amount = 0
    if Payment:
        payments_7d_count = Payment.objects.filter(created_at__date__gte=seven_days_ago).count()
        payments_7d_amount = (Payment.objects
                              .filter(created_at__date__gte=seven_days_ago, status=Payment.Status.ACCEPTED)
                              .aggregate(total=Sum("amount"))["total"] or 0)

    stats = {
        "missions": Mission.objects.count(),
        "missions_published": Mission.objects.filter(status="published").count(),
        "signups": MissionSignup.objects.count(),
        "signups_pending": MissionSignup.objects.filter(status=MissionSignup.Status.PENDING).count(),
        "events_upcoming": events_upcoming,
        "projects": projects_total,
        "volunteers": volunteers_total,
        "docs_total": docs_total,
        "docs_submitted": docs_pending_review,
        "applications_pending": applications_pending,
        "hours_entries_7d": HoursEntry.objects.filter(date__gte=seven_days_ago).count(),
        "hours_7d": hours_7d_sum,
        "payments_7d_count": payments_7d_count,
        "payments_7d_amount": payments_7d_amount,
    }

    # -------- Missions à venir/en cours (dates Mission) + taux de remplissage --------
    missions_qs = (
        Mission.objects.filter(status="published")
        .filter(Q(end_date__date__gte=today) | Q(start_date__date__gte=today))
        .annotate(accepted_count=Count("signups", filter=Q(signups__status=MissionSignup.Status.ACCEPTED)))
        .select_related("event")
        .order_by("start_date", "end_date")[:8]
    )

    def _date_range_display(sd, ed):
        sd_d = sd.date() if hasattr(sd, "date") else sd
        ed_d = ed.date() if hasattr(ed, "date") else ed
        if sd_d and ed_d and sd_d != ed_d:
            return f"{sd_d:%d/%m/%Y} → {ed_d:%d/%m/%Y}"
        if sd_d:
            return f"{sd_d:%d/%m/%Y}"
        return "Dates à confirmer"

    upcoming = []
    for m in missions_qs:
        cap = m.capacity or 0
        acc = getattr(m, "accepted_count", 0) or 0
        pct = int(round((acc / cap) * 100)) if cap else None
        upcoming.append({
            "mission_id": m.id,
            "title": m.title,
            "date": _date_range_display(m.start_date, m.end_date),
            "location": m.location or (getattr(m.event, "location", "") or ""),
            "accepted": acc,
            "capacity": cap,
            "fill_pct": pct,  # None si pas de capacité
        })

    # -------- Inscriptions en attente (les plus anciennes d'abord) --------
    pending_qs = (
        MissionSignup.objects
        .select_related("mission", "volunteer__user")
        .filter(status=MissionSignup.Status.PENDING)
        .order_by("created_at")[:10]
    )
    pending = [{
        "signup_id": s.id,
        "volunteer_name": s.volunteer.display_name,
        "mission_title": s.mission.title,
        "created_at": s.created_at,
    } for s in pending_qs]

    # -------- Documents à vérifier (soumis/en vérif) --------
    documents_review = []
    if hasattr(UserDocument, "status"):
        docs_qs = (UserDocument.objects
                   .select_related("user")
                   .filter(status__in=["submitted", "under_review"])
                   .order_by("-uploaded_at")[:8])
        for d in docs_qs:
            documents_review.append({
                "id": d.id,
                "name": d.name or (getattr(d.file, "name", "") or "Document"),
                "user": getattr(d.user, "get_full_name", lambda: d.user.username)(),
                "status": d.status,
                "uploaded_at": d.uploaded_at,
            })

    # -------- Top bénévoles du mois (par heures) --------
    top_volunteers = []
    top_qs = (HoursEntry.objects
              .filter(date__gte=start_month)
              .values("volunteer", "volunteer__name",
                      "volunteer__user__first_name", "volunteer__user__last_name")
              .annotate(total=Sum("hours"))
              .order_by("-total")[:5])
    for r in top_qs:
        label = r.get("volunteer__name") or f"{r.get('volunteer__user__first_name','')} {r.get('volunteer__user__last_name','')}".strip()
        top_volunteers.append({"volunteer_id": r["volunteer"], "name": label or "Bénévole", "hours": r["total"] or 0})

    # -------- Tendances d’heures (30 jours) --------
    raw = (HoursEntry.objects.filter(date__range=[start_30, today])
           .values("date").order_by("date").annotate(total=Sum("hours")))
    by_date = {row["date"]: float(row["total"] or 0.0) for row in raw}
    max_val = max([0.0] + list(by_date.values()))
    hours_series = []
    for i in range(30):
        d = start_30 + timedelta(days=i)
        v = float(by_date.get(d, 0.0))
        pct = 0 if max_val == 0 else int(round((v / max_val) * 100))
        hours_series.append({"date": d, "value": v, "height": pct})

    # -------- Projets “actifs” (avec missions à venir via Event) --------
    projects_active = (Project.objects
                       .annotate(
                           upcoming_missions=Count(
                               "events__missions",
                               filter=Q(events__missions__status="published") &
                                      (Q(events__missions__end_date__date__gte=today) |
                                       Q(events__missions__start_date__date__gte=today)),
                               distinct=True
                           ),
                           events_count=Count("events", distinct=True),
                       )
                       .order_by("-upcoming_missions", "title")[:5])

    projects_rows = [{
        "id": p.id,
        "title": getattr(p, "title", str(p)),
        "events_count": getattr(p, "events_count", 0),
        "upcoming_missions": getattr(p, "upcoming_missions", 0),
        "slug": getattr(p, "slug", None),
    } for p in projects_active]

    # -------- Notifications récentes --------
    notifications = []
    unread_count = 0
    if Notification:
        n_qs = Notification.objects.filter(recipient=request.user).order_by("-created_at")[:6]
        notifications = [{
            "id": n.id,
            "title": n.title or str(n),
            "message": n.message,
            "url": n.url or "",
            "is_read": n.is_read,
            "created_at": n.created_at,
        } for n in n_qs]
        unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()

    # -------- Paiements récents (si module présent) --------
    payments = []
    if Payment:
        pay_qs = (Payment.objects
                  .order_by("-created_at")
                  .values("id", "amount", "currency", "status", "provider", "created_at")[:5])
        payments = list(pay_qs)

    context = {
        "stats": stats,
        "upcoming": upcoming,
        "pending": pending,
        "documents_review": documents_review,
        "top_volunteers": top_volunteers,
        "hours": hours_series,
        "projects_rows": projects_rows,
        "notifications": notifications,
        "unread_count": unread_count,
        "payments": payments,
    }
    return render(request, "staff/dashboard.html", context)

# --------- ÉVÉNEMENTS (staff) ---------

@staff_member_required
def events_list(request):
    q = (request.GET.get("q") or "").strip()
    dfrom = request.GET.get("from") or ""
    dto   = request.GET.get("to") or ""
    project_id = request.GET.get("project") or ""

    qs = (Event.objects
          .prefetch_related("projects")
          .annotate(missions_count=Count("missions")))

    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(location__icontains=q))
    if dfrom: qs = qs.filter(date__gte=dfrom)
    if dto:   qs = qs.filter(date__lte=dto)
    if project_id.isdigit():
        qs = qs.filter(projects__id=int(project_id))

    page_obj = Paginator(qs.order_by("-date", "-id"), 15).get_page(request.GET.get("page"))
    projects = Project.objects.order_by("title").only("id", "title")

    rows = []
    for e in page_obj.object_list:
        rows.append({
            "id": e.id,
            "title": e.title,
            "date": e.date,
            "location": e.location or "",
            "projects": ", ".join(p.title for p in e.projects.all()) or "—",
            "missions_count": getattr(e, "missions_count", 0),
        })
    return render(request, "staff/events_list.html", {"page_obj": page_obj, "rows": rows, "projects": projects})

@staff_member_required
def event_detail(request, pk):
    event = get_object_or_404(Event.objects.prefetch_related("projects", "missions"), pk=pk)

    # petites données utiles pour l’UI
    projects = list(event.projects.all())
    missions = list(event.missions.select_related("event").order_by("start_date", "id"))

    return render(request, "staff/event_detail.html", {
        "event": event,
        "projects": projects,
        "missions": missions,
    })


@staff_member_required
@require_auth_key(
    action="event.create",
    level=AuthorizationKey.Level.HIGH,
    superuser_bypass=True,
    return_403=True,
    methods=("POST",),
)
def event_create(request):
    initial = {}
    project_id = request.GET.get("project")
    if project_id and project_id.isdigit():
        initial["projects"] = [int(project_id)]
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            e = form.save()
            messages.success(request, "Événement créé.")
            return redirect("staff:event_detail", pk=e.pk)
    else:
        form = EventForm(initial=initial)
    return render(request, "staff/event_form.html", {"form": form})


@staff_member_required
@require_auth_key(
    action="event.update",
    level=AuthorizationKey.Level.MEDIUM,
    superuser_bypass=True,
    return_403=True,
    methods=("POST",),
)
def event_update(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, "Événement mis à jour.")
            return redirect("staff:event_detail", pk=event.pk)
    else:
        form = EventForm(instance=event)
    return render(request, "staff/event_form.html", {"form": form, "event": event})


# --------- INSCRIPTIONS (listing staff) ---------

@staff_member_required
def signups_list(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    dfrom = _parse_date(request.GET.get("from"))
    dto   = _parse_date(request.GET.get("to"))

    qs = MissionSignup.objects.select_related("mission", "volunteer__user").all()
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(mission__title__icontains=q) |
            Q(volunteer__name__icontains=q) |
            Q(volunteer__user__username__icontains=q) |
            Q(volunteer__user__first_name__icontains=q) |
            Q(volunteer__user__last_name__icontains=q)
        )
    if dfrom:
        qs = qs.filter(created_at__date__gte=dfrom)
    if dto:
        qs = qs.filter(created_at__date__lte=dto)

    rows = [{
        "id": s.id,
        "volunteer_name": s.volunteer.display_name,
        "mission_title": s.mission.title,
        "status": s.status,
        "created_at": s.created_at,
    } for s in qs.order_by("-id")]

    page_obj = _paginate(request, rows, per_page=20)
    return render(request, "staff/signups_list.html", {"page_obj": page_obj})


# --------- BÉNÉVOLES ---------

@staff_member_required
def volunteers_list(request):
    q = (request.GET.get("q") or "").strip()
    skill = (request.GET.get("skill") or "").strip()

    qs = Volunteer.objects.select_related("user").all()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(email__icontains=q) |
            Q(phone__icontains=q) |
            Q(user__username__icontains=q) |
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q)
        )

    # Préfetch pour compétences
    skills_map = {}
    if skill:
        # filtrage par compétence demandée
        vs_qs = (VolunteerSkill.objects
                 .select_related("skill", "volunteer")
                 .filter(skill__name__icontains=skill))
    else:
        vs_qs = VolunteerSkill.objects.select_related("skill", "volunteer")

    for vs in vs_qs:
        skills_map.setdefault(vs.volunteer_id, []).append(vs.skill.name)

    rows = []
    for v in qs.order_by("name", "user__username"):
        rows.append({
            "id": v.id,
            "name": v.display_name,
            "username": v.user.username,
            "email": v.email or v.user.email,
            "phone": v.phone,
            "skills": ", ".join(sorted(skills_map.get(v.id, []))) or None,
        })

    page_obj = _paginate(request, rows, per_page=20)
    return render(request, "staff/volunteers_list.html", {"page_obj": page_obj})


@staff_member_required
def volunteer_detail(request, pk):
    v = get_object_or_404(Volunteer.objects.select_related("user"), pk=pk)

    # Invitation en cours (non utilisée & non expirée)
    pending_invite = TeamMemberInvite.objects.filter(
        member__user=v.user,
        used_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).order_by("-created_at").first()

    # Invitabilité : a un user + un email + pas déjà team_member
    can_invite = bool(
        getattr(v, "user", None)
        and (v.email or getattr(v.user, "email", ""))
        and not getattr(v.user, "team_member_id", None)
    )

    # Heures & stats
    hours_qs = (
        HoursEntry.objects
        .filter(volunteer=v)
        .select_related("mission", "event")
        .order_by("-date", "-id")
    )
    stats = {
        "hours": hours_qs.aggregate(total=Sum("hours"))["total"] or 0,
        "missions": hours_qs.exclude(mission__isnull=True).values_list("mission", flat=True).distinct().count(),
        "events": hours_qs.exclude(event__isnull=True).values_list("event", flat=True).distinct().count(),
    }

    # Inscriptions missions
    signups_qs = (
        MissionSignup.objects
        .filter(volunteer=v)
        .select_related("mission")
        .order_by("-id")
    )
    signups = [
        {
            "id": s.id,
            "mission_title": getattr(s.mission, "title", "—"),
            "status": s.status,
            "created_at": s.created_at,
        }
        for s in signups_qs
    ]

    # Compétences & dispos
    skills = list(
        VolunteerSkill.objects.filter(volunteer=v)
        .select_related("skill")
        .order_by("-level", "skill__name")
    )
    availability = list(
        Availability.objects.filter(volunteer=v)
        .order_by("day", "slot")
    )

    # Heures + pièces
    proofs_map = {}
    for p in HoursEntryProof.objects.filter(hours_entry__volunteer=v).select_related("hours_entry"):
        proofs_map.setdefault(p.hours_entry_id, []).append({
            "url": getattr(p.file, "url", ""),
            "name": p.original_name or getattr(p.file, "name", ""),
            "size": p.size,
        })

    hours = [
        {
            "date": h.date,
            "hours": h.hours,
            "note": h.note,
            "mission_title": getattr(h.mission, "title", None),
            "event_title": getattr(h.event, "title", None),
            "proofs": proofs_map.get(h.id, []),
        }
        for h in hours_qs
    ]

    context = {
        "volunteer": v,
        "stats": stats,
        "signups": signups,
        "skills": skills,
        "availability": availability,
        "hours": hours,
        "pending_invite": pending_invite,
        "can_invite": can_invite,
    }

    # ✅ IMPORTANT : un SEUL context, pas d'argument supplémentaire
    return render(request, "staff/volunteer_detail.html", context)

# --- INVITER UN VOLONTAIRE À REJOINDRE L'ÉQUIPE (par volontaire) ----------------
@staff_member_required
@require_auth_key(action="team.invite.one", level=AuthorizationKey.Level.MEDIUM, superuser_bypass=True, methods=("POST",), return_403=True)
def staff_volunteer_send_team_invite(request, volunteer_id: int):
    """
    Invite un VOLONTAIRE (par son id) à intégrer l'équipe.
    - Si un TeamMember lié à ce User existe, on le réutilise.
    - Sinon on crée un TeamMember minimal (user + name/email synchronisés).
    - On crée un TeamMemberInvite (token aléatoire) et on envoie l’email
      vers la page de complétion : /team/complete/<token> (ou reverse('team_complete', token)).
    """
    # Volunteer + User
    v = get_object_or_404(Volunteer.objects.select_related("user"), pk=volunteer_id)

    # On exige un compte utilisateur ou au moins un email
    target_email = None
    if getattr(v, "email", None):
        target_email = v.email
    if getattr(v, "user", None) and getattr(v.user, "email", None):
        # priorité à l’email du compte
        target_email = v.user.email

    if not target_email:
        messages.error(request, "Ce bénévole n’a pas d’email. Impossible d’envoyer l’invitation.")
        return redirect("staff:volunteer_detail", pk=v.pk)

    if not getattr(v, "user", None):
        messages.error(request, "Ce bénévole n’est pas lié à un compte utilisateur. Associez un User d’abord.")
        return redirect("staff:volunteer_detail", pk=v.pk)

    user = v.user

    # TeamMember : réutiliser si déjà lié à ce user, sinon créer minimal
    member = getattr(user, "team_member", None)
    if not member:
        member = TeamMember.objects.create(
            user=user,
            name=(user.get_full_name() or user.get_username() or v.display_name or "").strip() or "Membre",
            role="Membre",  # valeur par défaut; pourra être ajustée dans la fiche
            email=target_email,
            is_active=True,
        )

    # Créer l’invitation (token + expiry via model.save())
    invite = TeamMemberInvite.objects.create(
        member=member,
        created_by=request.user,
        message=(request.POST.get("message") or "").strip()[:2000] if request.method == "POST" else "",
    )

    # URL de complétion (on respecte ton existant avec reverse('team_complete', token) sinon fallback)
    try:
        accept_url = request.build_absolute_uri(reverse("team_complete", args=[invite.token]))
    except Exception:
        accept_url = request.build_absolute_uri(f"/team/complete/{invite.token}/")

    ctx = {
        "member": member,
        "invite": invite,
        "url": accept_url,
        "expires_at": invite.expires_at,
        "volunteer": v,
    }

    subject = f"Complétez votre accès équipe — {getattr(settings, 'SITE_NAME', 'Notre site')}"
    body_txt = render_to_string("staff/team/team_member_invite.txt", ctx)
    body_html = render_to_string("staff/team/team_member_invite.html", ctx)

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or "ne_pas_repondre@bamuwellbeing.org"
    try:
        send_mail(subject, body_txt, from_email, [target_email], html_message=body_html)
        messages.success(request, f"Invitation envoyée à {target_email} ✅")
    except Exception as e:
        messages.error(request, f"Erreur d’envoi de l’invitation : {e}")

    return redirect("staff:volunteer_detail", pk=v.pk)

# --------- DOCUMENTS ---------

@staff_member_required
def documents_review(request):
    # MàJ de statut (optionnel)
    if request.method == "POST":
        doc_id = request.POST.get("id")
        new_status = (request.POST.get("status") or "").strip()
        if doc_id and hasattr(UserDocument, "status"):
            try:
                d = UserDocument.objects.get(pk=doc_id)
                d.status = new_status
                d.save(update_fields=["status"])
                messages.success(request, "Statut mis à jour.")
            except UserDocument.DoesNotExist:
                messages.error(request, "Document introuvable.")
        return redirect("staff:documents_review")

    q = (request.GET.get("q") or "").strip()
    ftype = (request.GET.get("type") or "all").strip()
    status = (request.GET.get("status") or "").strip()

    qs = UserDocument.objects.select_related("user").order_by("-uploaded_at")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(file__icontains=q))
    if ftype == "images":
        qs = qs.filter(mime__startswith="image/")
    elif ftype == "pdf":
        qs = qs.filter(mime="application/pdf")
    if status and hasattr(UserDocument, "status"):
        qs = qs.filter(status=status)

    rows = [{
        "id": d.id,
        "name": d.name or getattr(d.file, "name", ""),
        "file_url": getattr(d.file, "url", ""),
        "user_name": d.user.get_full_name() or d.user.get_username(),
        "mime": d.mime,
        "size": d.size,
        "status": getattr(d, "status", ""),
    } for d in qs]

    page_obj = _paginate(request, rows, per_page=20)
    return render(request, "staff/documents_review.html", {"page_obj": page_obj})


# --------- HEURES ---------

@staff_member_required
def hours_list(request):
    q = (request.GET.get("q") or "").strip()
    dfrom = _parse_date(request.GET.get("from"))
    dto   = _parse_date(request.GET.get("to"))
    has_proofs = request.GET.get("has_proofs")

    qs = HoursEntry.objects.select_related("volunteer__user", "mission", "event").all()
    if q:
        qs = qs.filter(
            Q(note__icontains=q) |
            Q(mission__title__icontains=q) |
            Q(event__title__icontains=q) |
            Q(volunteer__name__icontains=q) |
            Q(volunteer__user__username__icontains=q) |
            Q(volunteer__user__first_name__icontains=q) |
            Q(volunteer__user__last_name__icontains=q)
        )
    if dfrom:
        qs = qs.filter(date__gte=dfrom)
    if dto:
        qs = qs.filter(date__lte=dto)

    # pièces jointes
    proofs_qs = HoursEntryProof.objects.filter(hours_entry__in=qs)
    proofs_map = {}
    for p in proofs_qs:
        proofs_map.setdefault(p.hours_entry_id, []).append({
            "url": getattr(p.file, "url", ""),
            "name": p.original_name or getattr(p.file, "name", ""),
            "size": p.size,
        })

    rows = []
    for e in qs.order_by("-date", "-id"):
        proofs = proofs_map.get(e.id, [])
        if has_proofs == "yes" and not proofs:
            continue
        if has_proofs == "no" and proofs:
            continue
        rows.append({
            "date": e.date,
            "volunteer_name": e.volunteer.display_name,
            "mission_title": getattr(e.mission, "title", None),
            "event_title": getattr(e.event, "title", None),
            "hours": e.hours,
            "note": e.note,
            "proofs": proofs,
        })

    page_obj = _paginate(request, rows, per_page=20)
    return render(request, "staff/hours_list.html", {"page_obj": page_obj})


# Accepter une candidature (par le staff)
@staff_member_required
@require_POST
def staff_signup_accept(request, signup_id):
    s = get_object_or_404(MissionSignup.objects.select_related("mission"), pk=signup_id)

    # (facultatif) n'autoriser que depuis invited/pending
    if s.status not in {MissionSignup.Status.INVITED, MissionSignup.Status.PENDING}:
        messages.warning(request, "Cette candidature ne peut pas être acceptée depuis son statut actuel.")
        return redirect(request.META.get("HTTP_REFERER") or "staff:signups_list")

    # (facultatif) vérifier la capacité
    if s.mission.capacity:
        accepted = s.mission.signups.filter(status=MissionSignup.Status.ACCEPTED).count()
        if accepted >= s.mission.capacity:
            messages.error(request, "Capacité maximale déjà atteinte pour cette mission.")
            return redirect(request.META.get("HTTP_REFERER") or "staff:signups_list")

    s.status = MissionSignup.Status.ACCEPTED
    s.responded_at = timezone.now()
    s.save(update_fields=["status", "responded_at"])
    messages.success(request, "Candidature acceptée ✅")
    return redirect(request.META.get("HTTP_REFERER") or "staff:signups_list")


# Refuser une candidature (par le staff)
@staff_member_required
@require_POST
def staff_signup_decline(request, signup_id):
    s = get_object_or_404(MissionSignup, pk=signup_id)
    if s.status == MissionSignup.Status.ACCEPTED:
        messages.warning(request, "Impossible de refuser une candidature déjà acceptée.")
        return redirect(request.META.get("HTTP_REFERER") or "staff:signups_list")

    s.status = MissionSignup.Status.DECLINED
    s.responded_at = timezone.now()
    s.save(update_fields=["status", "responded_at"])
    messages.info(request, "Candidature refusée.")
    return redirect(request.META.get("HTTP_REFERER") or "staff:signups_list")




def _redirect_to_signup_parent(request, signup):
    # Privilégie ?next=… / Referer ; sinon retombe sur le détail de mission
    nxt = request.POST.get("next") or request.GET.get("next") or request.META.get("HTTP_REFERER")
    if nxt:
        return nxt
    try:
        return reverse("staff:mission_detail", args=[signup.mission_id])
    except Exception:
        return reverse("staff:mission_list")


# -------- TEAM --------
@staff_member_required
def staff_team_list(request):
    qs = TeamMember.objects.all()
    q = (request.GET.get("q") or "").strip()
    dept = (request.GET.get("department") or "").strip()
    seniority = (request.GET.get("seniority") or "").strip()
    active = request.GET.get("active")  # 'yes' | 'no' | None

    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(role__icontains=q) |
            Q(expertise__icontains=q) | Q(department__icontains=q)
        )
    if dept:
        qs = qs.filter(department__icontains=dept)
    if seniority:
        qs = qs.filter(seniority=seniority)
    if active == "yes":
        qs = qs.filter(is_active=True)
    elif active == "no":
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "staff/team/team_list.html", {
        "page_obj": page_obj,
        "qs_params": request.GET.urlencode(),
    })

@staff_member_required
def staff_user_json(request, pk):
    u = get_object_or_404(User, pk=pk, is_active=True)
    data = {
        "id": u.pk,
        "username": u.get_username(),
        "first_name": u.first_name or "",
        "last_name": u.last_name or "",
        "full_name": (u.get_full_name() or "").strip(),
        "email": u.email or "",
    }
    return JsonResponse(data)

@staff_member_required
@require_auth_key(
    action="team.create",
    level=AuthorizationKey.Level.HIGH,
    superuser_bypass=True,
)
def staff_team_create(request):
    if request.method == "POST":
        form = TeamMemberForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Membre ajouté ✅")
            return redirect("staff:team_detail", slug=obj.slug)
        messages.error(request, "Veuillez corriger les erreurs.")
    else:
        form = TeamMemberForm()

    return render(request, "staff/team/team_form.html", {"form": form, "member": None})


@staff_member_required
@require_auth_key(
    action="team.update",  # ⬅️ corrige l'ancien "mission.update"
    level=AuthorizationKey.Level.HIGH,
    superuser_bypass=True,
)
def staff_team_update(request, slug):
    member = get_object_or_404(TeamMember, slug=slug)
    if request.method == "POST":
        form = TeamMemberForm(request.POST, request.FILES, instance=member)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Modifications enregistrées ✅")
            # si le slug a changé (nom modifié), on suit la nouvelle URL
            return redirect("staff:team_detail", slug=obj.slug)
        messages.error(request, "Veuillez corriger les erreurs.")
    else:
        form = TeamMemberForm(instance=member)

    return render(request, "staff/team/team_form.html", {"form": form, "member": member})


@staff_member_required
def staff_team_detail(request, slug):
    member = get_object_or_404(TeamMember, slug=slug)
    can_approve = False
    try:
        if request.user.is_superuser and getattr(member, "user", None) and not member.user.is_staff:
            qs = member.invites.all()
            # Consider accepted responses, and legacy invites without a recorded response but used
            can_approve = qs.filter(response="accepted").exists() or qs.filter(response="", used_at__isnull=False).exists()
    except Exception:
        can_approve = False
    is_owner = bool(getattr(member, "user_id", None) and request.user.is_authenticated and member.user_id == request.user.id)
    can_manage_invites = bool(request.user.is_superuser)
    return render(
        request,
        "staff/team/team_detail.html",
        {"member": member, "can_approve": can_approve, "is_owner": is_owner, "can_manage_invites": can_manage_invites},
    )

# -------- PARTNERS --------
@staff_member_required
def staff_partner_list(request):
    qs = Partenaire.objects.all()
    q = (request.GET.get("q") or "").strip()
    category = (request.GET.get("category") or "").strip()
    tier = (request.GET.get("tier") or "").strip()
    active = request.GET.get("active")  # 'yes' | 'no' | None
    has_website = request.GET.get("has_website")  # 'yes'

    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
    if category:
        qs = qs.filter(category=category)
    if tier:
        qs = qs.filter(tier=tier)
    if active == "yes":
        qs = qs.filter(is_active=True)
    elif active == "no":
        qs = qs.filter(is_active=False)
    if has_website == "yes":
        qs = qs.exclude(website__isnull=True).exclude(website="")

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "staff/partners/partner_list.html", {
        "page_obj": page_obj,
        "qs_params": request.GET.urlencode(),
    })

@staff_member_required
@require_auth_key(
    action="patner.create",
    level=AuthorizationKey.Level.HIGH,
    superuser_bypass=True,
    return_403=True,
    methods=("POST",),   # clé exigée UNIQUEMENT à l’envoi
)
def staff_partner_create(request):
    if request.method == "POST":
        form = PartenaireForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Partenaire créé ✅")
            return redirect("staff:partner_detail", slug=obj.slug)
        messages.error(request, "Veuillez corriger les erreurs.")
    else:
        form = PartenaireForm()

    return render(request, "staff/partners/partner_form.html", {"form": form, "partner": None})

@staff_member_required
@require_auth_key(
    action="patner.update",
    level=AuthorizationKey.Level.MEDIUM,
    superuser_bypass=True,
    return_403=True,
    methods=("POST",),   # clé exigée UNIQUEMENT à l’envoi
)
def staff_partner_update(request, slug):
    partner = get_object_or_404(Partenaire, slug=slug)
    if request.method == "POST":
        form = PartenaireForm(request.POST, request.FILES, instance=partner)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Modifications enregistrées ✅")
            return redirect("staff:partner_detail", slug=obj.slug)
        messages.error(request, "Veuillez corriger les erreurs.")
    else:
        form = PartenaireForm(instance=partner)

    return render(request, "staff/partners/partner_form.html", {"form": form, "partner": partner})

@staff_member_required
def staff_partner_detail(request, slug):
    partner = get_object_or_404(Partenaire, slug=slug)
    return render(request, "staff/partners/partner_detail.html", {"partner": partner})

# Alias public (pas besoin d’être staff)
def staff_partner_detail_alias(request, slug):
    partner = get_object_or_404(Partenaire, slug=slug)
    return render(request, "core/partner_detail_alias.html", {"partner": partner})


# --------- CANDIDATURE BÉNÉVOLE ---------
import os
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .models import VolunteerApplication, VolunteerApplicationDocument, ApplicationStatus

# ---- helpers ----
def user_is_volunteer(user) -> bool:
    # profil Volunteer existant ? (et approuvé s'il y a un champ status)
    try:
        v = user.volunteer
        if hasattr(v, "status"):
            return v.status == "approved"
        return True
    except Exception:
        pass
    # groupe fallback
    if user.groups.filter(name="Bénévoles").exists():
        return True
    # candidature approuvée fallback
    return VolunteerApplication.objects.filter(user=user, status=ApplicationStatus.APPROVED).exists()

IMAGE_EXTS = {".png",".jpg",".jpeg",".webp",".gif"}
def _is_image(field_file) -> bool:
    name = (getattr(field_file, "name", None) or str(field_file)).split("?",1)[0].split("#",1)[0]
    return name.lower().endswith(tuple(IMAGE_EXTS))


# ---- public (utilisateur) ----
@login_required
def application_start(request):
    # Blocage si déjà bénévole
    if user_is_volunteer(request.user):
        messages.info(request, "Vous êtes déjà bénévole approuvé.")
        return redirect("benevoles:dashboard")  # adapte la cible

    # Rediriger vers candidature ouverte existante
    existing = VolunteerApplication.objects.filter(
        user=request.user, status__in=[ApplicationStatus.PENDING, ApplicationStatus.NEEDS_CHANGES]
    ).order_by("-submitted_at").first()
    if existing:
        messages.info(request, "Vous avez déjà une candidature en cours.")
        return redirect("benevoles:application_detail", pk=existing.pk)

    if request.method == "POST":
        form = VolunteerApplicationForm(request.POST)
        formset = DocumentFormSet(request.POST, request.FILES, queryset=VolunteerApplicationDocument.objects.none())
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                app = form.save(commit=False)
                app.user = request.user
                app.status = ApplicationStatus.PENDING
                app.save()
                for f in formset:
                    if f.cleaned_data and f.cleaned_data.get("file"):
                        d = f.save(commit=False)
                        d.application = app
                        d.status = "pending"
                        d.save()
            messages.success(request, "Candidature envoyée. Elle sera examinée par l’équipe.")
            return redirect("benevoles:application_detail", pk=app.pk)
        messages.error(request, "Merci de corriger les erreurs dans le formulaire.")
    else:
        initial = {}
        if request.user.get_full_name():
            initial["full_name"] = request.user.get_full_name()
        form = VolunteerApplicationForm(initial=initial)
        formset = DocumentFormSet(queryset=VolunteerApplicationDocument.objects.none())

    return render(request, "benevoles_candidature/application_form.html", {
        "form": form,
        "formset": formset,
    })


@login_required
def application_detail(request, pk):
    app = get_object_or_404(VolunteerApplication, pk=pk, user=request.user)
    docs = app.documents.all().order_by("doc_type", "-uploaded_at")

    # Image principale
    main_image_url = None
    for d in docs:
        if d.doc_type == "selfie" and hasattr(d.file, "url") and _is_image(d.file):
            main_image_url = d.file.url; break
    if not main_image_url:
        for d in docs:
            if d.doc_type == "id_front" and hasattr(d.file, "url") and _is_image(d.file):
                main_image_url = d.file.url; break
    if not main_image_url:
        for d in docs:
            if hasattr(d.file, "url") and _is_image(d.file):
                main_image_url = d.file.url; break

    allow_add  = app.status in [ApplicationStatus.NEEDS_CHANGES, ApplicationStatus.PENDING]
    allow_edit = allow_add

    if request.method == "POST":
        action = request.POST.get("action", "").strip()

        if action == "update_infos" and allow_edit:
            edit_form = VolunteerApplicationForm(request.POST, instance=app)
            formset = DocumentFormSet(queryset=VolunteerApplicationDocument.objects.none())

            if edit_form.is_valid():
                obj = edit_form.save(commit=False)
                if app.status == ApplicationStatus.NEEDS_CHANGES:
                    obj.status = ApplicationStatus.PENDING
                obj.save()
                messages.success(request, "Informations mises à jour.")
                return redirect(app.get_absolute_url())

            messages.error(request, "Merci de corriger les erreurs dans le formulaire.")

        elif action == "add_docs" and allow_add:
            edit_form = VolunteerApplicationForm(instance=app)
            formset = DocumentFormSet(
                request.POST, request.FILES,
                queryset=VolunteerApplicationDocument.objects.none()
            )

            if formset.is_valid():
                added = 0
                with transaction.atomic():
                    for f in formset:
                        if getattr(f, "cleaned_data", None) and f.cleaned_data.get("file"):
                            d = f.save(commit=False)
                            d.application = app
                            d.status = "pending"
                            d.save()
                            added += 1

                if added and app.status == ApplicationStatus.NEEDS_CHANGES:
                    app.status = ApplicationStatus.PENDING
                    app.save(update_fields=["status"])

                messages.success(request, f"{added} document(s) ajouté(s).")
                return redirect(app.get_absolute_url())

            messages.error(request, "Erreurs dans les documents envoyés.")

        else:
            return redirect(app.get_absolute_url())

    else:
        edit_form = VolunteerApplicationForm(instance=app)
        formset = DocumentFormSet(queryset=VolunteerApplicationDocument.objects.none())

    return render(request, "benevoles_candidature/application_detail.html", {
        "app": app,
        "docs": docs,
        "allow_add": allow_add,
        "allow_edit": allow_edit,
        "edit_form": edit_form,
        "formset": formset,
        "main_image_url": main_image_url,
    })


# ---- staff ----
@staff_member_required
def staff_applications_list(request):
    qs = VolunteerApplication.objects.all().select_related("user", "reviewed_by")
    status = request.GET.get("status")
    if status:
        qs = qs.filter(status=status)
    return render(request, "staff/applications_list.html", {"apps": qs, "status": status})

# ⬇️ import du système d’auth par clé
from staff.security.services import verify_and_consume_key
from staff.security.models import AuthorizationKey  # pour AuthorizationKey.Level

@staff_member_required
def staff_application_review(request, pk):
    app = get_object_or_404(VolunteerApplication, pk=pk)
    docs = app.documents.all().order_by("doc_type", "-uploaded_at")

    if request.method == "POST":
        action = request.POST.get("action")
        note = (request.POST.get("note") or "").strip()

        # helpers pour log context
        obj_pk = str(app.pk)
        obj_repr = f"VolunteerApplication#{app.pk}"
        meta = {"view": "staff_application_review"}

        if action == "approve":
            # ⬇️ clé **moyenne** obligatoire
            ok = verify_and_consume_key(
                request,
                action="application_approve",
                required_level=AuthorizationKey.Level.MEDIUM,
                object_pk=obj_pk,
                object_repr=obj_repr,
                meta=meta,
            )
            if not ok:
                messages.error(request, "Clé d’autorisation requise (niveau moyen) pour approuver.")
                return redirect("staff:application_review", pk=app.pk)

            app.approve(request.user)
            messages.success(request, "Candidature approuvée.")
            return redirect("staff:applications_list")

        elif action == "unapprove":
            # ⬇️ clé **critique** obligatoire
            ok = verify_and_consume_key(
                request,
                action="application_unapprove",
                required_level=AuthorizationKey.Level.CRITICAL,  # ou HIGH si ta constante s’appelle HIGH
                object_pk=obj_pk,
                object_repr=obj_repr,
                meta=meta,
            )
            if not ok:
                messages.error(request, "Clé d’autorisation critique requise pour annuler l’approbation.")
                return redirect("staff:application_review", pk=app.pk)

            app.unapprove(request.user, note=note)
            messages.warning(request, "Approbation annulée. La candidature repasse en corrections.")
            return redirect("staff:application_review", pk=app.pk)

        elif action == "reject":
            if app.status == ApplicationStatus.APPROVED:
                messages.error(request, "Impossible de refuser une candidature déjà approuvée. Annulez d’abord l’approbation.")
                return redirect("staff:application_review", pk=app.pk)
            # (optionnel) tu peux exiger aussi une clé (niveau moyen), sinon on laisse comme avant
            app.reject(request.user, note=note)
            messages.warning(request, "Candidature refusée.")
            return redirect("staff:applications_list")

        elif action == "needs_changes":
            if app.status == ApplicationStatus.APPROVED:
                messages.error(request, "Candidature approuvée : utilisez « Annuler l’approbation » pour demander des corrections.")
                return redirect("staff:application_review", pk=app.pk)
            # (optionnel) clé niveau bas/moyen ici si tu veux
            app.request_changes(request.user, note=note)
            messages.info(request, "Corrections demandées au candidat.")
            return redirect("staff:application_review", pk=app.pk)

        elif action in ("doc_approve", "doc_reject"):
            # Toujours verrou doctrinal si approuvée
            if app.status == ApplicationStatus.APPROVED:
                messages.info(request, "Candidature approuvée : utilisez « Annuler l’approbation » pour réviser les documents.")
                return redirect("staff:application_review", pk=app.pk)

            doc_id = request.POST.get("doc_id")
            doc = get_object_or_404(VolunteerApplicationDocument, pk=doc_id, application=app)
            doc.status = "approved" if action == "doc_approve" else "rejected"
            doc.reviewed_by = request.user
            doc.reviewed_at = timezone.now()
            doc.reviewer_note = note
            doc.save(update_fields=["status", "reviewed_by", "reviewed_at", "reviewer_note"])
            messages.success(request, f"Document « {doc.get_doc_type_display()} » mis à jour.")
            return redirect("staff:application_review", pk=app.pk)

    return render(request, "staff/application_review.html", {"app": app, "docs": docs})
    

@staff_member_required
@require_auth_key(
    action="team.invite.bulk",
    level=AuthorizationKey.Level.MEDIUM,
    superuser_bypass=True,
    methods=("POST",),           # clé demandée uniquement sur POST
    return_403=True,             # si fetch/AJAX tu auras un 403 JSON
)
def team_invite_picker(request):
    """
    Liste les bénévoles invitables (pas déjà staff, pas déjà invités valides).
    - GET: filtres + liste + bouton 'Inviter' par ligne + sélection multiple
    - POST: envoi d’invitations pour la sélection (bulk)
    """
    f = InviteFilterForm(request.GET or None)

    # Base: tous les bénévoles avec user (pour que l’accès équipe fonctionne)
    qs = Volunteer.objects.select_related("user").filter(user__isnull=False)

    # Exclure: déjà TeamMember
    qs = qs.exclude(user__team_member__isnull=False)

    # Exclure: déjà une invitation encore valide
    valid_invites = TeamMemberInvite.objects.filter(
        used_at__isnull=True, expires_at__gt=timezone.now()
    ).values_list("member__user_id", flat=True)
    qs = qs.exclude(user_id__in=valid_invites)

    # Filtres
    if f.is_valid():
        q     = f.cleaned_data.get("q") or ""
        skill = f.cleaned_data.get("skill") or ""
        day   = f.cleaned_data.get("day") or ""
        slot  = f.cleaned_data.get("slot") or ""
        only_available = bool(f.cleaned_data.get("only_available"))

        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(email__icontains=q) |
                Q(phone__icontains=q) |
                Q(user__username__icontains=q) |
                Q(user__first_name__icontains=q) |
                Q(user__last_name__icontains=q)
            )

        # Si tu as un modèle Skill/Availability, tu peux appliquer skill/day/slot comme tu le fais ailleurs
        # (omise ici pour rester concis)

        # only_available: on garde, car on a déjà exclu staff/invités
        # tu peux ajouter d’autres règles spécifiques si besoin

    paginator = Paginator(qs.order_by("name", "user__username"), 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    # POST = envoi bulk
    if request.method == "POST":
        ids = request.POST.getlist("volunteer_ids")
        sent = 0
        for vid in ids:
            v = Volunteer.objects.select_related("user").filter(pk=vid).first()
            if not v or not v.user:
                continue
            # Par sécurité: saute si déjà staff ou déjà invitée valide
            if hasattr(v.user, "team_member"):
                continue
            has_valid = TeamMemberInvite.objects.filter(
                member__user=v.user, used_at__isnull=True, expires_at__gt=timezone.now()
            ).exists()
            if has_valid:
                continue

            # Créer (ou réutiliser) TeamMember lié à ce user
            member = getattr(v.user, "team_member", None)
            if not member:
                member = TeamMember.objects.create(
                    user=v.user,
                    name=(v.display_name or v.user.get_full_name() or v.user.get_username() or "Membre").strip(),
                    email=v.email or v.user.email or "",
                    role="Membre",
                    is_active=True,
                )

            invite = TeamMemberInvite.objects.create(member=member, created_by=request.user)
            # Envoi mail (comme ta vue unitaire)
            try:
                accept_url = request.build_absolute_uri(
                    reverse("team_complete", args=[invite.token])
                )
            except Exception:
                accept_url = request.build_absolute_uri(f"/team/complete/{invite.token}/")

            ctx = {"member": member, "invite": invite, "url": accept_url, "expires_at": invite.expires_at, "volunteer": v}
            subject = f"Complétez votre accès équipe — {getattr(settings, 'SITE_NAME', 'Notre site')}"
            body_txt = render_to_string("staff/team/team_member_invite.txt", ctx)
            body_html = render_to_string("staff/team/team_member_invite.html", ctx)

            from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "ne_pas_repondre@bamuwellbeing.org")
            to_email = v.email or v.user.email
            if to_email:
                try:
                    send_mail(subject, body_txt, from_email, [to_email], html_message=body_html)
                    sent += 1
                except Exception:
                    pass

        if sent:
            messages.success(request, f"{sent} invitation(s) envoyée(s).")
        else:
            messages.info(request, "Aucune invitation envoyée (déjà staff, déjà invité·e, ou sans email).")
        return redirect("staff:team_invite_picker")

    return render(request, "staff/team/team_invite_picker.html", {
        "form": f,
        "page_obj": page_obj,
    })

@staff_member_required
@require_auth_key(
    action="team.invite.revoke",
    level=AuthorizationKey.Level.MEDIUM,  # mets HIGH/CRITICAL si tu veux plus strict
    superuser_bypass=True,
    methods=("POST",),
    return_403=True,
)
def team_invite_revoke(request, invite_id: int):
    invite = get_object_or_404(TeamMemberInvite, pk=invite_id)

    # pour revenir à la fiche bénévole si possible
    vol_id = getattr(getattr(invite.member.user, "volunteer", None), "id", None)

    # Invalider l'invitation (sans la supprimer pour garder la traçabilité)
    # - si ton modèle a revoked_at, on le renseigne ; sinon on force expires_at à maintenant.
    try:
        setattr(invite, "revoked_at", timezone.now())
        invite.expires_at = timezone.now()
        invite.save(update_fields=["expires_at", "revoked_at"])
    except Exception:
        invite.expires_at = timezone.now()
        invite.save(update_fields=["expires_at"])

    messages.success(request, "Invitation annulée.")

    if vol_id:
        return redirect("staff:volunteer_detail", pk=vol_id)
    # fallback
    return redirect(request.META.get("HTTP_REFERER") or "staff:team_list")


@staff_member_required
@require_auth_key(
    action="team.invite.resend",
    level=AuthorizationKey.Level.MEDIUM,
    superuser_bypass=True,
    methods=("POST",),
    return_403=True,
)
def team_invite_resend(request, invite_id: int):
    invite = get_object_or_404(TeamMemberInvite, pk=invite_id)
    member = invite.member

    # Expire l’invitation existante (et note 'revoked_at' si le champ existe)
    try:
        setattr(invite, "revoked_at", timezone.now())
        invite.expires_at = timezone.now()
        invite.save(update_fields=["expires_at", "revoked_at"])
    except Exception:
        invite.expires_at = timezone.now()
        invite.save(update_fields=["expires_at"])

    # Crée une nouvelle invitation
    new_invite = TeamMemberInvite.objects.create(member=member, created_by=request.user)

    # URL de complétion
    try:
        accept_url = request.build_absolute_uri(reverse("team_complete", args=[new_invite.token]))
    except Exception:
        accept_url = request.build_absolute_uri(f"/team/complete/{new_invite.token}/")

    ctx = {"member": member, "invite": new_invite, "url": accept_url, "expires_at": new_invite.expires_at}
    subject = f"Complétez votre accès équipe · {getattr(settings, 'SITE_NAME', 'Notre site')}"
    body_txt = render_to_string("staff/team/team_member_invite.txt", ctx)
    body_html = render_to_string("staff/team/team_member_invite.html", ctx)

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "ne_pas_repondre@bamuwellbeing.org")
    to_email = member.email or (getattr(member.user, "email", None) if member.user else None)
    if to_email:
        try:
            send_mail(subject, body_txt, from_email, [to_email], html_message=body_html)
            messages.success(request, "Invitation renvoyée.")
        except Exception:
            messages.warning(request, "Invitation recréée mais l’envoi d’email a échoué.")
    else:
        messages.info(request, "Invitation recréée. Aucun email n’est renseigné sur le membre.")

    return redirect("staff:team_detail", slug=member.slug)

# Override with enhanced logic: deactivate also revokes staff access
@staff_member_required
@require_auth_key(
    action="team.member.toggle",
    level=AuthorizationKey.Level.MEDIUM,
    superuser_bypass=True,
    methods=("POST",),
    return_403=True,
)
def team_member_toggle_active(request, slug):
    member = get_object_or_404(TeamMember, slug=slug)
    member.is_active = not member.is_active
    member.save(update_fields=["is_active"])

    if not member.is_active and getattr(member, "user", None):
        try:
            u = member.user
            changed = []
            if u.is_staff:
                u.is_staff = False
                changed.append("is_staff")
            if changed:
                u.save(update_fields=changed)
            try:
                from django.contrib.auth.models import Group
                team_group = Group.objects.filter(name="Team").first()
                if team_group:
                    team_group.user_set.remove(u)
            except Exception:
                pass
        except Exception:
            pass

    messages.info(request, f"Statut du membre mis à jour.")
    return redirect("staff:team_detail", slug=member.slug)

# --- Approve staff access for a team member (supervised) ---
@staff_member_required
@user_passes_test(lambda u: u.is_superuser)
@require_auth_key(
    action="team.approve_access",
    level=AuthorizationKey.Level.HIGH,
    superuser_bypass=True,
    methods=("POST",),
    return_403=True,
)
def team_member_approve_access(request, slug):
    member = get_object_or_404(TeamMember, slug=slug)
    u = getattr(member, "user", None)
    if not u:
        messages.error(request, "Aucun compte utilisateur lié à ce membre.")
        return redirect("staff:team_detail", slug=member.slug)
    changed = []
    if not u.is_staff:
        u.is_staff = True
        changed.append("is_staff")
    try:
        from django.contrib.auth.models import Group
        team_group, _ = Group.objects.get_or_create(name="Team")
        u.groups.add(team_group)
    except Exception:
        pass
    if changed:
        u.save(update_fields=changed)
    messages.success(request, "Accès staff accordé.")
    return redirect("staff:team_detail", slug=member.slug)


@staff_member_required
@require_auth_key(
    action="team.member.toggle",
    level=AuthorizationKey.Level.MEDIUM,
    superuser_bypass=True,
    methods=("POST",),
    return_403=True,
)
def team_member_toggle_active(request, slug):
    member = get_object_or_404(TeamMember, slug=slug)
    member.is_active = not member.is_active
    member.save(update_fields=["is_active"])
    messages.info(request, f"Membre {'réactivé' if member.is_active else 'désactivé'}.")
    return redirect("staff:team_detail", slug=member.slug)
