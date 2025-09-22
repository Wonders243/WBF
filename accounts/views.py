# accounts/views.py
import os
import mimetypes
from decimal import Decimal
from datetime import datetime, time as dtime, date as ddate, timedelta
from pathlib import Path


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.forms import ModelForm, DateInput
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render, resolve_url
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.db import IntegrityError
from django.core.paginator import Paginator
from core.models import Event
from staff.models import Mission, MissionSignup  # <-- IMPORTANT
from .forms import VolunteerForm, AvailabilityAddForm, VolunteerSkillAddForm, HoursEntryForm
from django.core.exceptions import ValidationError
from core.utils import redirect_back 
from staff.security.services import require_auth_key

from django.utils.http import url_has_allowed_host_and_scheme
from staff.models import VolunteerApplication, ApplicationStatus
from .models import EmailChangeRequest, PhoneVerification
from allauth.account.models import EmailAddress



from .views_helpers import create_hours_proof  # ⬅️ import du helper



from .models import (
    UserDocument,
    Volunteer,
    HoursEntry,
    HoursEntryProof,
    Availability, VolunteerSkill,
)
from django.utils.http import url_has_allowed_host_and_scheme

# --------- Upload / Documents ----------
PROTECTED_STATUSES = {
    "verified", "verifie", "approuve", "approved", "valide",
    "verification", "under_review", "pending", "en_verification", "en_attente_verification",
}
MAX_UPLOAD_MB = 5
ALLOWED_MIME_PREFIXES = ("image/",)
ALLOWED_MIMES = {"application/pdf"}

PROOFS_MAX_SIZE = 5 * 1024 * 1024
PROOFS_ALLOWED_MIMES = {"application/pdf", "image/jpeg", "image/png", "image/webp"}




# --------- Dashboard ----------

@login_required
@never_cache
def dashboard(request):
    volunteer = Volunteer.objects.filter(user=request.user).first()
    if not volunteer or getattr(volunteer, "status", None) != "approved":
        messages.info(request, "Vous n’êtes pas encore bénévole.")
        return redirect_back(request)

    today = timezone.localdate()
    start_30 = today - timedelta(days=29)
    start_month = today.replace(day=1)

    # ======= Missions à venir ou en cours =======
    signups = (
        MissionSignup.objects
        .filter(volunteer=volunteer, status=MissionSignup.Status.ACCEPTED)
        .select_related("mission")
        .filter(Q(mission__end_date__gte=today) | Q(mission__start_date__gte=today))
        .order_by("mission__start_date", "mission__end_date")[:5]
    )

    def _state_for(m):
        sd, ed = getattr(m, "start_date", None), getattr(m, "end_date", None)
        if hasattr(sd, "date"): sd = sd.date()
        if hasattr(ed, "date"): ed = ed.date()
        if sd and ed and sd <= today <= ed:
            return "En cours"
        if sd and sd > today:
            return "À venir"
        return "—"

    def _date_display(m):
        sd, ed = getattr(m, "start_date", None), getattr(m, "end_date", None)
        if hasattr(sd, "date"): sd = sd.date()
        if hasattr(ed, "date"): ed = ed.date()
        if sd and ed and sd != ed:
            return f"{sd:%d/%m/%Y} → {ed:%d/%m/%Y}"
        if sd:
            return f"{sd:%d/%m/%Y}"
        return "Dates à confirmer"

    upcoming = []
    for s in signups:
        m = s.mission
        upcoming.append({
            "title": m.title,
            "date_display": _date_display(m),
            "location": m.location or "Lieu à confirmer",
            "state": _state_for(m),
            "signup_id": s.id,
            "detail_url": getattr(m, "get_absolute_url", lambda: None)(),
        })

    # Fallback lien détails missions (si pas de get_absolute_url)
    try:
        from django.urls import reverse
        for it in upcoming:
            if not it.get("detail_url"):
                it["detail_url"] = reverse("benevoles:missions_browse")
    except Exception:
        pass

    # ======= Documents récents =======
    documents_qs = UserDocument.objects.filter(user=request.user).order_by("-uploaded_at")[:8]
    documents = [{
        "name": d.name or os.path.basename(getattr(d.file, "name", "")),
        "date": getattr(d, "uploaded_at", None) or getattr(d, "created_at", None),
        "obj": d,
    } for d in documents_qs]

    # ======= Heures cumulées =======
    total_hours = volunteer.hours_entries.aggregate(total=Sum("hours"))["total"] or Decimal("0")
    month_hours = volunteer.hours_entries.filter(date__gte=start_month).aggregate(total=Sum("hours"))["total"] or Decimal("0")

    # ======= KPI =======
    missions_count = volunteer.hours_entries.filter(mission__isnull=False).values("mission").distinct().count()
    events_total = Event.objects.count()
    events_next = Event.objects.filter(date__gte=today).count()

    # ======= Tâches =======
    tasks = _build_volunteer_tasks(volunteer, today)

    # ======= Sparkline 30 jours =======
    raw = (volunteer.hours_entries.filter(date__range=[start_30, today])
           .values("date").order_by("date").annotate(total=Sum("hours")))
    hours_by_date = {row["date"]: float(row["total"] or 0) for row in raw}
    max_val = max([0.0] + list(hours_by_date.values()))
    hours_series = []
    for i in range(30):
        d = start_30 + timedelta(days=i)
        v = float(hours_by_date.get(d, 0.0))
        pct = 0 if max_val == 0 else int(round((v / max_val) * 100))
        hours_series.append({"date": d, "value": v, "height": pct})

    stats = {
        "hours": total_hours,
        "hours_month": month_hours,
        "missions": missions_count,
        "missions_active": missions_count,
        "events": events_total,
        "events_next": events_next,
    }

    return render(request, "accounts/dashboard.html", {
        "volunteer": volunteer,
        "stats": stats,
        "upcoming_missions": upcoming,  # <-- aligne avec le template
        "tasks": tasks,
        "hours": hours_series,
        "documents": documents,
    })



# ========= Helpers — tasks for dashboard =========
def _build_volunteer_tasks(volunteer, today):
    from django.shortcuts import resolve_url as _resolve
    tasks = []  # ← corrige la récursion

    # Invitations à traiter
    try:
        inv_count = MissionSignup.objects.filter(volunteer=volunteer, status=MissionSignup.Status.INVITED).count()
        if inv_count:
            tasks.append({
                "key": "invitations",
                "title": "Répondre aux invitations",
                "desc": "Vous avez des invitations à confirmer ou refuser.",
                "count": inv_count,
                "url": _resolve("benevoles:missions_browse") + "#invitations",
                "variant": "warning",
                "action": "Voir",
            })
    except Exception:
        pass

    # Demandes en attente
    try:
        pending_count = MissionSignup.objects.filter(volunteer=volunteer, status=MissionSignup.Status.PENDING).count()
        if pending_count:
            tasks.append({
                "key": "applications",
                "title": "Suivre mes demandes",
                "desc": "Des demandes de mission sont en cours de validation.",
                "count": pending_count,
                "url": _resolve("benevoles:missions_browse") + "#applications",
                "variant": "info",
                "action": "Ouvrir",
            })
    except Exception:
        pass

    # Profil incomplet
    try:
        missing_bits = []
        if not (volunteer.phone or "").strip():
            missing_bits.append("téléphone")
        if not getattr(volunteer, "avatar", None):
            missing_bits.append("photo")
        if missing_bits:
            tasks.append({
                "key": "profile",
                "title": "Compléter mon profil",
                "desc": "Manque : " + ", ".join(missing_bits),
                "count": None,
                "url": _resolve("benevoles:profile_benevole"),
                "variant": "muted",
                "action": "Éditer",
            })
    except Exception:
        pass

    # Heures manquantes sur missions passées
    try:
        need_hours = 0
        qs = MissionSignup.objects.select_related("mission").filter(
            volunteer=volunteer, status=MissionSignup.Status.ACCEPTED
        )
        for s in qs:
            m = s.mission
            sd, ed = getattr(m, "start_date", None), getattr(m, "end_date", None)
            if hasattr(sd, "date"): sd = sd.date()
            if hasattr(ed, "date"): ed = ed.date()
            # Fin retenue (fallback : start)
            end_date = ed or sd
            if end_date and end_date < today:
                if not HoursEntry.objects.filter(volunteer=volunteer, mission=m).exists():
                    need_hours += 1
        if need_hours:
            tasks.append({
                "key": "hours",
                "title": "Déclarer mes heures",
                "desc": "Des missions passées sans déclaration d'heures.",
                "count": need_hours,
                "url": _resolve("benevoles:hours_entry_create"),
                "variant": "primary",
                "action": "Déclarer",
            })
    except Exception:
        pass

    return tasks


# --------- Page Missions (invitations + demandes + missions disponibles) ----------
@login_required
@never_cache
@login_required
def missions_browse(request):
    volunteer = Volunteer.objects.filter(user=request.user).first()
    if not volunteer:
        messages.info(request, "Vous n’êtes pas encore bénévole.")
        return redirect_back(request)  # <= renvoie là d’où l’utilisateur vient # ou une page d’explication

    today = timezone.localdate()

    # --- Helpers : parse GET dates (YYYY-MM-DD) & normalize date/datetime ---
    def _parse_date(param):
        val = (request.GET.get(param) or "").strip()
        if not val:
            return None
        try:
            return datetime.strptime(val, "%Y-%m-%d").date()
        except Exception:
            return None

    def _first(*vals):
        for v in vals:
            if v is not None:
                return v
        return None

    def _date_only(d):
        if d is None:
            return None
        if isinstance(d, ddate):
            return d
        if isinstance(d, datetime):
            return d.date()
        return None

    def _is_past(d):
        if d is None:
            return False
        try:
            if isinstance(d, datetime):
                return d.date() < today
            if isinstance(d, ddate):
                return d < today
        except Exception:
            return False
        return False

    # Aliases acceptés: start/end, from/to, date_from/date_to, (FR) de/à
    date_start = _first(_parse_date("start"), _parse_date("from"), _parse_date("date_from"), _parse_date("de"))
    date_end   = _first(_parse_date("end"),   _parse_date("to"),   _parse_date("date_to"),   _parse_date("a"))

    # -------------------- 1) INVITATIONS DU STAFF (status=INVITED) --------------------
    invitations_qs = (
        MissionSignup.objects
        .filter(volunteer=volunteer, status=MissionSignup.Status.INVITED)
        .select_related("mission", "mission__event")
        .order_by("mission__event__date", "mission__start_date", "id")
    )
    if date_start:
        invitations_qs = invitations_qs.filter(
            Q(mission__event__date__gte=date_start)
            | Q(mission__start_date__date__gte=date_start)
            | Q(mission__start_date__gte=date_start)
        )
    if date_end:
        invitations_qs = invitations_qs.filter(
            Q(mission__event__date__lte=date_end)
            | Q(mission__start_date__date__lte=date_end)
            | Q(mission__start_date__lte=date_end)
        )

    invitations = []
    for s in invitations_qs:
        ev = s.mission.event
        raw_date = getattr(ev, "date", None) or getattr(s.mission, "start_date", None)
        d = _date_only(raw_date)
        location = (getattr(ev, "location", "") or s.mission.location or "")
        inv_title = s.mission.title
        try:
            if ev and getattr(ev, "title", None):
                inv_title = f"{s.mission.title} — {ev.title}"
        except Exception:
            pass
        invitations.append({
            "signup_id": s.id,
            "mission_id": s.mission_id,
            "title": inv_title,
            "date": d,
            "location": location,
            "status": s.status,          # "invited"
            "is_past": _is_past(d),
        })

    # -------------------- 2) MES DEMANDES ENVOYÉES (status=PENDING) -------------------
    applications_qs = (
        MissionSignup.objects
        .filter(volunteer=volunteer, status=MissionSignup.Status.PENDING)
        .select_related("mission", "mission__event")
        .order_by("mission__event__date", "mission__start_date", "id")
    )
    if date_start:
        applications_qs = applications_qs.filter(
            Q(mission__event__date__gte=date_start)
            | Q(mission__start_date__date__gte=date_start)
            | Q(mission__start_date__gte=date_start)
        )
    if date_end:
        applications_qs = applications_qs.filter(
            Q(mission__event__date__lte=date_end)
            | Q(mission__start_date__date__lte=date_end)
            | Q(mission__start_date__lte=date_end)
        )
 
    applications = []
    for s in applications_qs:
        ev = s.mission.event
        raw_date = getattr(ev, "date", None) or getattr(s.mission, "start_date", None)
        d = _date_only(raw_date)  # doit renvoyer un objet date ou None
        location = (getattr(ev, "location", "") or s.mission.location or "")
        is_past = _is_past(d)

        # Ici tu n'as que des PENDING dans le QS, donc True… sauf si tu veux bloquer l'annulation pour les missions passées
        can_cancel = (s.status in {
            MissionSignup.Status.PENDING,
            getattr(MissionSignup.Status, "INVITED", "invited"),
            getattr(MissionSignup.Status, "ACCEPTED", "accepted"),
        }) and not is_past

        app_title = s.mission.title
        try:
            if ev and getattr(ev, "title", None):
                app_title = f"{s.mission.title} — {ev.title}"
        except Exception:
            pass
        applications.append({
            "signup_id": s.id,
            "mission_id": s.mission_id,
            "title": app_title,
            "date": d,
            "location": location,
            "status": s.status,      # "pending"
            "is_past": is_past,
            "can_cancel": can_cancel,
        })


    # -------------------- 3) MISSIONS DISPONIBLES --------------------
    q = (request.GET.get("q") or "").strip()
    statuses_block = [MissionSignup.Status.ACCEPTED, MissionSignup.Status.PENDING, MissionSignup.Status.INVITED]

    base_qs = Mission.objects.filter(status="published").select_related("event")

    # Si un intervalle est fourni -> filtre sur cet intervalle; sinon -> futur uniquement
    if date_start or date_end:
        avail_qs = base_qs
        if date_start:
            avail_qs = avail_qs.filter(
                Q(event__date__gte=date_start)
                | Q(start_date__date__gte=date_start)
                | Q(start_date__gte=date_start)
            )
        if date_end:
            avail_qs = avail_qs.filter(
                Q(event__date__lte=date_end)
                | Q(start_date__date__lte=date_end)
                | Q(start_date__lte=date_end)
            )
    else:
        avail_qs = base_qs.filter(
            Q(event__date__gte=today)
            | Q(start_date__date__gte=today)
            | Q(start_date__gte=today)
        )

    # Exclure les missions où le bénévole a déjà une inscription active
    avail_qs = (
        avail_qs
        .exclude(signups__volunteer=volunteer, signups__status__in=statuses_block)
        .order_by("event__date", "start_date", "id")
    )

    if q:
        avail_qs = avail_qs.filter(
            Q(title__icontains=q) | Q(description__icontains=q) | Q(location__icontains=q) | Q(event__title__icontains=q)
        )

    paginator = Paginator(avail_qs, 9)
    page_obj = paginator.get_page(request.GET.get("page"))

    available = []
    for m in page_obj.object_list:
        ev = m.event
        raw_date = getattr(ev, "date", None) or getattr(m, "start_date", None)
        d = _date_only(raw_date)
        location = (getattr(ev, "location", "") or m.location or "")
        available.append({
            "mission_id": m.id,
            "title": m.title,
            "event": getattr(ev, "title", ""),
            "date": d,
            "location": location,
            "capacity": m.capacity,
            "is_past": _is_past(d),
        })

    return render(request, "accounts/missions_browse.html", {
        "q": q,
        "invitations": invitations,     # 1) Staff -> bénévole répond
        "applications": applications,   # 2) Bénévole -> en attente staff
        "available": available,         # 3) Catalogue
        "page_obj": page_obj,
        "start": date_start,
        "end": date_end,
    })

# --------- Reste des vues : documents / heures / profil / notifications ----------
@login_required
@never_cache

def UserDocuments_list(request):
    qs = UserDocument.objects.filter(user=request.user).order_by("-uploaded_at")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(file__icontains=q))

    ftype = request.GET.get("type", "all")
    if ftype == "images":
        qs = qs.filter(mime__startswith="image/")
    elif ftype == "pdf":
        qs = qs.filter(mime="application/pdf")

    status_param = request.GET.get("status", "").strip()
    if status_param and hasattr(UserDocument, "status"):
        qs = qs.filter(status__iexact=status_param)

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    status_choices = []
    if hasattr(UserDocument, "status"):
        field = UserDocument._meta.get_field("status")
        if getattr(field, "choices", None):
            status_choices = [c[0] for c in field.choices]

    ctx = {"page_obj": page_obj, "docs": page_obj.object_list, "q": q,
           "ftype": ftype, "status_param": status_param, "status_choices": status_choices,
           "max_upload_mb": MAX_UPLOAD_MB}
    return render(request, "accounts/documents_list.html", ctx)


@login_required
@never_cache
def UserDocuments_upload(request):
    if request.method != "POST":
        return redirect("benevoles:UserDocuments_list")
    files = request.FILES.getlist("files")
    if not files:
        messages.error(request, "Aucun fichier sélectionné.")
        return redirect("benevoles:UserDocuments_list")

    ok, ko = 0, 0
    for f in files:
        mime = getattr(f, "content_type", "") or ""
        size = getattr(f, "size", 0) or 0
        if size > MAX_UPLOAD_MB * 1024 * 1024:
            ko += 1; messages.error(request, f"« {f.name} » dépasse {MAX_UPLOAD_MB} Mo."); continue
        if not (mime.startswith(ALLOWED_MIME_PREFIXES) or mime in ALLOWED_MIMES):
            ko += 1; messages.error(request, f"« {f.name} » n'est pas un type autorisé (images/PDF)."); continue

        doc = UserDocument(user=request.user, file=f, name=Path(f.name).stem[:120], mime=mime, size=size)
        if hasattr(UserDocument, "status"):
            try: doc.status = "submitted"
            except Exception: pass
        doc.save(); ok += 1

    if ok: messages.success(request, f"{ok} fichier(s) téléversé(s) avec succès.")
    if ko and not ok: messages.error(request, "Aucun fichier n'a été téléversé.")
    return redirect("benevoles:UserDocuments_list")


@login_required
@never_cache
def UserDocuments_delete(request, pk):
    try:
        doc = UserDocument.objects.get(pk=pk)
    except UserDocument.DoesNotExist:
        raise Http404("Document introuvable")
    if request.method != "POST":
        return HttpResponseForbidden("Méthode non autorisée")

    def _status_str(d): return (str(getattr(d, "status", "") or "")).lower()
    if doc.user_id != request.user.id or (_status_str(doc) in PROTECTED_STATUSES):
        messages.error(request, "Ce document ne peut pas être supprimé.")
        return redirect("benevoles:UserDocuments_list")

    f = doc.file; doc.delete()
    if f and hasattr(f, "storage"):
        try: f.storage.delete(f.name)
        except Exception: pass
    messages.success(request, "Document supprimé.")
    return redirect("benevoles:UserDocuments_list")




@login_required
@require_POST
def hours_proof_upload(request, entry_id):
    entry = get_object_or_404(HoursEntry, pk=entry_id, volunteer__user=request.user)
    files = request.FILES.getlist("files")
    ok, ko = 0, []
    for f in files:
        if f.size > PROOFS_MAX_SIZE:
            ko.append((f.name, "Fichier trop volumineux (max 5 Mo)")); continue
        mime, _ = mimetypes.guess_type(f.name)
        if mime not in PROOFS_ALLOWED_MIMES:
            ko.append((f.name, "Type non autorisé")); continue
        HoursEntryProof.objects.create(hours_entry=entry, file=f, original_name=f.name); ok += 1
    if ok: messages.success(request, f"{ok} justificatif(s) ajouté(s).")
    if ko:
        details = "; ".join(f"{n} ({e})" for n, e in ko)
        messages.error(request, f"Certains fichiers refusés : {details}")
    return redirect("benevoles:historique_benevole")

@login_required
@never_cache
def _create_proof(entry, uploaded_file, user):
    """
    Création robuste du justificatif même si les noms de champs diffèrent.
    - Trouve automatiquement le champ fichier (FileField/ImageField)
    - Trouve le FK vers HoursEntry (souvent 'entry')
    - Renseigne 'uploaded_by' si présent
    """
    Proof = HoursEntryProof
    model_fields = {f.name: f for f in Proof._meta.get_fields()}

    # Trouver le champ fichier
    file_field_name = None
    for name, f in model_fields.items():
        try:
            it = f.get_internal_type()
        except Exception:
            continue
        if it in {"FileField", "ImageField"}:
            file_field_name = name
            break
    if not file_field_name:
        file_field_name = "file"  # fallback

    # Trouver le champ FK vers HoursEntry
    entry_fk_name = None
    for name, f in model_fields.items():
        if getattr(f, "is_relation", False) and getattr(f, "related_model", None) is HoursEntry:
            entry_fk_name = name
            break
    if not entry_fk_name:
        entry_fk_name = "entry"  # fallback

    kwargs = {
        entry_fk_name: entry,
        file_field_name: uploaded_file,
    }
    if "uploaded_by" in model_fields:
        kwargs["uploaded_by"] = user

    Proof.objects.create(**kwargs)


def _safe_back(request, fallback="benevoles:historique_benevole"):
    return (request.POST.get("next")
            or request.GET.get("next")
            or resolve_url(fallback))


def _safe_back(request, fallback="benevoles:historique_benevole"):
    return (request.POST.get("next") or request.GET.get("next") or resolve_url(fallback))

@login_required
def hours_entry_create(request):
    volunteer = getattr(request.user, "volunteer", None)
    if volunteer is None:
        messages.error(request, "Créez d’abord votre profil bénévole.")
        return redirect("benevoles:dashboard")

    if request.method == "POST":
        form = HoursEntryForm(
            request.POST, request.FILES, user=request.user,
            instance=HoursEntry(volunteer=volunteer)
        )

        # 1,5 → 1.5 (norme décimale)
        if "hours" in request.POST and "," in request.POST.get("hours", ""):
            form.data = form.data.copy()
            form.data["hours"] = request.POST["hours"].replace(",", ".")

        if form.is_valid():
            # La DATE est fixée dans le form.save() (automatique)
            entry = form.save(commit=False)

            # Lier l'event si manquant
            if getattr(entry, "event_id", None) is None and entry.mission:
                try:
                    entry.event = entry.mission.event
                except Exception:
                    pass

            try:
                entry.save()  # peut lever ValidationError (contraintes modèle)
            except ValidationError as e:
                for msg in getattr(e, "messages", [str(e)]):
                    form.add_error(None, msg)
                return render(request, "accounts/hours_entry_form.html", {"form": form})

            # Attacher le justificatif
            uploaded = form.cleaned_data.get("proof")
            if uploaded:
                try:
                    create_hours_proof(entry, uploaded, request.user)
                except Exception as e:
                    messages.warning(
                        request,
                        "Heures enregistrées, mais le justificatif n'a pas pu être attaché automatiquement. "
                        f"Détail: {e}"
                    )

            messages.success(request, "Heures enregistrées avec justificatif. Merci !")
            return redirect(_safe_back(request))

        messages.error(request, "Le formulaire contient des erreurs. Corrigez-les puis réessayez.")
        return render(request, "accounts/hours_entry_form.html", {"form": form})

    # GET
    form = HoursEntryForm(user=request.user, instance=HoursEntry(volunteer=volunteer))
    if form.fields["mission"].queryset.count() == 0:
        messages.info(request, "Aucune mission effectuée pour l’instant, rien à déclarer.")
    return render(request, "accounts/hours_entry_form.html", {"form": form})
# ---- Historique (ta template est déjà OK) ----

@login_required
@never_cache
def historique_benevole(request):
    user = request.user
    volunteer = Volunteer.objects.filter(user=user).first()
    if not volunteer:
        messages.info(request, "Vous n’êtes pas encore bénévole.")
        return redirect_back(request)

    # ---- Filtres GET
    q = (request.GET.get("q") or "").strip()
    type_filter = (request.GET.get("type") or "").strip()
    periode = (request.GET.get("periode") or "").strip()

    since = None
    if periode.isdigit():
        since = timezone.now() - timedelta(days=int(periode))

    # ---- Normalisation datetime "aware"
    def ensure_dt(value):
        if isinstance(value, datetime):
            return timezone.localtime(value) if timezone.is_aware(value) else timezone.make_aware(value, timezone.get_current_timezone())
        if isinstance(value, ddate):
            dt = datetime.combine(value, dtime(12, 0))
            return timezone.make_aware(dt, timezone.get_current_timezone())
        return timezone.now()

    items = []

    # ---- Heures & activités (missions / événements)
    he_q = (volunteer.hours_entries
            .select_related("mission", "event")
            .prefetch_related("proofs"))  # <-- important si tu as hours.proofs

    if since:
        he_q = he_q.filter(date__gte=since)

    if q:
        he_q = he_q.filter(
            Q(note__icontains=q) |
            Q(mission__title__icontains=q) |
            Q(event__title__icontains=q) |
            Q(mission__project__title__icontains=q) |
            Q(event__project__title__icontains=q)
        )

    # Construction des items (missions / events / heures simples)
    for he in he_q.order_by("-date", "-id"):
        if getattr(he, "mission_id", None):
            it_type = "mission"
            title = f"Mission — {he.mission.title}"
            descr = getattr(he.mission, "description", "") or (he.note or "")
            lieu = getattr(he.mission, "location", "") or ""
            projet = getattr(getattr(he.mission, "project", None), "title", "") or ""
        elif getattr(he, "event_id", None):
            it_type = "evenement"
            title = f"Événement — {he.event.title}"
            descr = getattr(he.event, "description", "") or (he.note or "")
            lieu = getattr(he.event, "location", "") or ""
            projet = getattr(getattr(he.event, "project", None), "title", "") or ""
        else:
            it_type = "heures"
            title = "Heures déclarées"
            descr, lieu, projet = he.note or "", "", ""

        if not type_filter or type_filter == it_type:
            # Preparer les URLs de justificatifs (si relation "proofs" existe)
            proof_urls = []
            if hasattr(he, "proofs"):
                for p in he.proofs.all():
                    url = getattr(getattr(p, "file", None), "url", "")
                    if url:
                        proof_urls.append(url)

            items.append({
                "type": it_type,
                "date": ensure_dt(he.date),
                "title": title,
                "description": descr,
                "projet": projet,
                "heures": f"{(he.hours or 0):g}h" if isinstance(he.hours, (int, float, Decimal)) else he.hours,
                "lieu": lieu,
                "status": getattr(he, "status", ""),
                "fichier_url": "",          # pour compat desc
                "proof_urls": proof_urls,   # <-- ajouté
            })

    # ---- Documents de l’utilisateur
    docs_q = user.documents.all()  # via related_name="documents" sur UserDocument.user
    if since:
        if hasattr(UserDocument, "uploaded_at"):
            docs_q = docs_q.filter(uploaded_at__gte=since)
        else:
            docs_q = docs_q.filter(created_at__gte=since)
    if q:
        docs_q = docs_q.filter(Q(name__icontains=q))

    for d in docs_q.order_by("-uploaded_at" if hasattr(UserDocument, "uploaded_at") else "-created_at"):
        if not type_filter or type_filter == "document":
            items.append({
                "type": "document",
                "date": ensure_dt(getattr(d, "uploaded_at", None) or getattr(d, "created_at", None)),
                "title": d.name or os.path.basename(getattr(d.file, "name", "")),
                "description": "",
                "projet": "",
                "heures": "",
                "lieu": "",
                "status": getattr(d, "status", ""),
                "fichier_url": getattr(getattr(d, "file", None), "url", ""),
                "proof_urls": [],  # pas de proofs pour les documents
            })

    # ---- Tri et stats
    items.sort(key=lambda x: x["date"], reverse=True)

    total_heures = he_q.aggregate(total=Sum("hours"))["total"] or Decimal("0")
    stats = {
        "missions": sum(1 for it in items if it["type"] == "mission"),
        "evenements": sum(1 for it in items if it["type"] == "evenement"),
        "heures": f"{total_heures:g}h",
    }
    total_count = len(items)

    # ---- Pagination
    paginator = Paginator(items, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "accounts/historique.html", {
        "page_obj": page_obj,
        "stats": stats,
        "total_count": total_count,
    })


def _to_aware(d):
    """Ton utilitaire existant ; garde-le si déjà défini ailleurs.
       Ici on le redéclare par sécurité minimale :"""
    if not d:
        return None
    # Si 'd' est une date (pas datetime), on la met à minuit en timezone locale
    if hasattr(d, "year") and not hasattr(d, "hour"):
        return timezone.make_aware(timezone.datetime(d.year, d.month, d.day), timezone.get_current_timezone())
    # Sinon on s'assure qu'elle est aware
    return timezone.localtime(d) if timezone.is_aware(d) else timezone.make_aware(d, timezone.get_current_timezone())

@login_required
def profile_benevole(request):
    volunteer = Volunteer.objects.filter(user=request.user).first()
    if not volunteer or getattr(volunteer, "status", None) != "approved":
        messages.info(request, "Vous n’êtes pas encore bénévole.")
        return redirect_back(request)

    # Heures & stats
    hours_qs = HoursEntry.objects.filter(volunteer=volunteer).select_related("mission", "event")
    total_hours = hours_qs.aggregate(total=Sum("hours"))["total"] or Decimal("0")
    missions_count = hours_qs.exclude(mission__isnull=True).values_list("mission", flat=True).distinct().count()
    events_count = hours_qs.exclude(event__isnull=True).values_list("event", flat=True).distinct().count()
    stats = {"hours": total_hours, "missions": missions_count, "events": events_count}

    # Données de profil
    availability = list(Availability.objects.filter(volunteer=volunteer).order_by("day", "slot"))
    skills = list(VolunteerSkill.objects.filter(volunteer=volunteer).select_related("skill"))
    documents = list(UserDocument.objects.filter(user=request.user).order_by("-uploaded_at")[:8])

    # Complétude du profil
    missing = []
    if not (volunteer.phone or "").strip():
        missing.append("téléphone")
    if not (volunteer.motivation or "").strip():
        missing.append("motivation")
    if not getattr(volunteer, "avatar", None):
        missing.append("photo")
    if not availability:
        missing.append("disponibilités")
    if not skills:
        missing.append("compétences")

    total_slots = 5  # phone, motivation, avatar, availability, skills
    filled = total_slots - len(missing)
    completeness = max(0, min(100, int((filled / total_slots) * 100)))

    # ===== Prochaines missions ACCEPTÉES : seulement les dates de mission =====
    today = timezone.localdate()

    signups = (
        MissionSignup.objects
        .filter(volunteer=volunteer, status=MissionSignup.Status.ACCEPTED)
        .select_related("mission")
        .filter(Q(mission__end_date__gte=today) | Q(mission__start_date__gte=today))
        .order_by("mission__start_date", "mission__end_date")[:5]
    )

    def _state_for(m):
        sd, ed = getattr(m, "start_date", None), getattr(m, "end_date", None)
        if hasattr(sd, "date"): sd = sd.date()
        if hasattr(ed, "date"): ed = ed.date()
        if sd and ed and sd <= today <= ed:
            return "En cours"
        if sd and sd > today:
            return "À venir"
        return "—"

    def _date_display(m):
        sd, ed = getattr(m, "start_date", None), getattr(m, "end_date", None)
        if hasattr(sd, "date"): sd = sd.date()
        if hasattr(ed, "date"): ed = ed.date()
        if sd and ed and sd != ed:
            return f"{sd:%d/%m/%Y} → {ed:%d/%m/%Y}"
        if sd:
            return f"{sd:%d/%m/%Y}"
        return "Dates à confirmer"

    upcoming = []
    for s in signups:
        m = s.mission
        # Clés pour compatibilité avec ton template (date/location),
        # + extras optionnels (date_display/state/detail_url)
        upcoming.append({
            "title": m.title,
            "date": getattr(m, "start_date", None),                 # utilisé tel quel dans ton template actuel
            "location": (m.location or "Lieu à confirmer"),
            "signup_id": s.id,
            "date_display": _date_display(m),                       # bonus : prêt à afficher
            "state": _state_for(m),                                 # bonus : "En cours" / "À venir"
            "detail_url": getattr(m, "get_absolute_url", lambda: None)(),
        })

    # Activité récente (heures + documents)
    activity = []
    for h in hours_qs.order_by("-date", "-id")[:5]:
        parts = []
        if h.mission: parts.append(str(h.mission))
        if h.event: parts.append(str(h.event))
        label = " – ".join(parts) if parts else "Déclaration d'heures"
        dt = _to_aware(h.date)
        activity.append({"title": f"{h.hours} h déclarées — {label}", "date": dt})

    for d in documents[:5]:
        activity.append({"title": f"Document ajouté — {d.name or d.file.name}", "date": _to_aware(d.uploaded_at)})

    now_aw = timezone.now()
    activity.sort(key=lambda x: x["date"] or now_aw, reverse=True)
    activity = activity[:8]

    return render(request, "accounts/profile.html", {
        "volunteer": volunteer,
        "stats": stats,
        "availability": availability,
        "skills": skills,
        "documents": documents,
        "activity": activity,
        "profile_missing": missing,
        "profile_completeness": completeness,
        "upcoming": upcoming,  # ← missions basées sur start/end de Mission (pas Event)
    })


@login_required
@never_cache
def profile_edit(request):
    volunteer, _ = Volunteer.objects.get_or_create(
        user=request.user,
        defaults={
            "name": request.user.get_full_name() or request.user.get_username(),
            "email": request.user.email,
        },
    )

    action = request.POST.get("action") if request.method == "POST" else None
    form = VolunteerForm(request.POST or None, request.FILES or None, instance=volunteer, user=request.user)

    av_form = AvailabilityAddForm(request.POST or None, volunteer=volunteer) if action == "add_availability" else AvailabilityAddForm(volunteer=volunteer)
    from .forms import AvailabilityBulkForm
    av_bulk_form = AvailabilityBulkForm(request.POST or None) if action in ("add_availability", "add_availability_bulk") else AvailabilityBulkForm()

    from .forms import VolunteerSkillAddForm
    skill_form = VolunteerSkillAddForm(request.POST or None, request.FILES or None, volunteer=volunteer) if action == "add_skill" else VolunteerSkillAddForm(volunteer=volunteer)

    availabilities = Availability.objects.filter(volunteer=volunteer).order_by("day", "slot")
    skills = VolunteerSkill.objects.filter(volunteer=volunteer).select_related("skill").order_by("-level", "skill__name")

    # Emails: ensure current primary exists
    try:
        if request.user.email:
            ea, _ = EmailAddress.objects.get_or_create(
                user=request.user,
                email=request.user.email,
                defaults={"primary": True, "verified": False},
            )
            if not ea.primary:
                EmailAddress.objects.filter(user=request.user).update(primary=False)
                ea.primary = True
                ea.save(update_fields=["primary"])
    except Exception:
        pass
    email_addresses = list(EmailAddress.objects.filter(user=request.user).order_by("-primary", "-verified", "email"))

    # pending phone verification (pour afficher le bloc dans le template)
    now = timezone.now()
    phone_verif = (PhoneVerification.objects
                   .filter(volunteer=volunteer, used_at__isnull=True, expires_at__gt=now)
                   .order_by("-created_at")
                   .first())

    if request.method == "POST":

        # --- Enregistrement du profil (ré-auth incluse via le form) ---
        if action == "profile":
            # Honeypot
            if (request.POST.get("hp_profile") or "").strip():
                messages.error(request, "Requête invalide.")
                return redirect("benevoles:profile_edit")

            if form.is_valid():
                orig_email = request.user.email
                new_email = (form.cleaned_data.get("email") or "").strip()
                new_phone = (form.cleaned_data.get("phone") or "").strip()

                # Sauvegarde (le form interdit de changer 'name')
                obj = form.save(commit=False)
                obj.save(); form.save_m2m()

                # Gestion email : on garde ta logique de vérification Allauth
                if new_email and new_email.lower() != (orig_email or "").lower():
                    from django.core.mail import EmailMessage
                    from django.template.loader import render_to_string
                    from .models import EmailChangeRequest
                    ecr = EmailChangeRequest.objects.create(user=request.user, new_email=new_email)
                    verify_url = request.build_absolute_uri(reverse("benevoles:email_change_verify", args=[ecr.token]))
                    body = render_to_string("accounts/emails/email_change.txt", {"user": request.user, "new_email": new_email, "verify_url": verify_url})
                    try:
                        EmailMessage(subject="Vérification de votre nouvel email", body=body, to=[new_email]).send(fail_silently=True)
                        messages.info(request, "Vérifiez votre nouveau mail pour confirmer le changement. L'ancien mail reste actif tant que non vérifié.")
                    except Exception:
                        messages.error(request, "Impossible d'envoyer l'email de vérification. L'ancien mail est conservé.")

                # Gestion téléphone : si changé → OTP SMS, on NE met PAS à jour tout de suite volunteer.phone
                if new_phone and new_phone != (volunteer.phone or ""):
                    pv = PhoneVerification.create_or_replace(volunteer, new_phone)
                    messages.info(request, "Un code de vérification a été envoyé par SMS. Saisissez-le ci-dessous pour confirmer votre numéro.")
                    # On n'écrase pas encore volunteer.phone : on le fera après code valide
                    phone_verif = pv  # pour que le bloc s'affiche immédiatement

                messages.success(request, "Profil mis à jour.")
                # Sync staff profil si lié
                try:
                    tm = getattr(request.user, "team_member", None)
                    if tm:
                        tm.phone = volunteer.phone or tm.phone
                        tm.email = request.user.email or tm.email
                        if hasattr(tm, "updated_at"):
                            tm.save(update_fields=["phone", "email", "updated_at"])
                        else:
                            tm.save()
                except Exception:
                    pass
                return redirect("benevoles:profile_edit")
            else:
                messages.error(request, "Veuillez corriger les erreurs du profil.")

        # --- Vérification du téléphone (OTP) ---
        elif action == "phone_verify":
            code = (request.POST.get("code") or "").strip()
            pv_id = request.POST.get("pv_id")
            pv_qs = PhoneVerification.objects.filter(volunteer=volunteer, used_at__isnull=True, expires_at__gt=timezone.now())
            if pv_id:
                pv_qs = pv_qs.filter(id=pv_id)
            pv = pv_qs.order_by("-created_at").first()

            if not pv:
                messages.error(request, "Aucune vérification en attente ou code expiré.")
                return redirect(f"{reverse('benevoles:profile_edit')}#profile")

            if pv.attempts >= 5:
                messages.error(request, "Trop de tentatives. Demandez un nouveau code.")
                return redirect(f"{reverse('benevoles:profile_edit')}#profile")

            if pv.is_expired():
                messages.error(request, "Code expiré. Demandez un nouveau code.")
                return redirect(f"{reverse('benevoles:profile_edit')}#profile")

            if code != pv.code:
                pv.attempts += 1
                pv.save(update_fields=["attempts"])
                messages.error(request, "Code incorrect.")
                return redirect(f"{reverse('benevoles:profile_edit')}#profile")

            # Succès : on valide le téléphone
            volunteer.phone = pv.phone
            volunteer.save(update_fields=["phone"])
            pv.mark_used()
            messages.success(request, "Numéro de téléphone vérifié et mis à jour.")
            return redirect(f"{reverse('benevoles:profile_edit')}#profile")

        elif action == "phone_resend":
            # Renvoi d’un nouveau code
            pending = PhoneVerification.objects.filter(volunteer=volunteer, used_at__isnull=True).order_by("-created_at").first()
            target_phone = pending.phone if pending else (volunteer.phone or "").strip()
            if not target_phone:
                messages.error(request, "Aucun numéro à vérifier.")
            else:
                pv = PhoneVerification.create_or_replace(volunteer, target_phone)
                messages.info(request, "Nouveau code envoyé par SMS.")
                phone_verif = pv
            return redirect(f"{reverse('benevoles:profile_edit')}#profile")

        # --- Disponibilités / Skills : inchangé ---
        elif action == "add_availability":
            if av_form.is_valid():
                try:
                    av_form.save()
                    messages.success(request, "Disponibilité ajoutée.")
                except IntegrityError:
                    messages.error(request, "Cette disponibilité existe déjà.")
                return redirect(f"{reverse('benevoles:profile_edit')}#availability")
            messages.error(request, "Veuillez corriger les erreurs de la disponibilité.")

        elif action == "delete_availability":
            pk = request.POST.get("id")
            Availability.objects.filter(pk=pk, volunteer=volunteer).delete()
            messages.success(request, "Disponibilité supprimée.")
            return redirect(f"{reverse('benevoles:profile_edit')}#availability")

        elif action == "add_skill":
            if skill_form.is_valid():
                try:
                    skill_form.save()
                    messages.success(request, "Compétence ajoutée.")
                except IntegrityError:
                    messages.error(request, "Cette compétence est déjà associée.")
                return redirect(f"{reverse('benevoles:profile_edit')}#skills")
            messages.error(request, "Veuillez corriger les erreurs des compétences.")

        elif action == "delete_skill":
            pk = request.POST.get("id")
            VolunteerSkill.objects.filter(pk=pk, volunteer=volunteer).delete()
            messages.success(request, "Compétence supprimée.")
            return redirect(f"{reverse('benevoles:profile_edit')}#skills")

    documents = UserDocument.objects.filter(user=request.user).order_by("-uploaded_at")[:12]

    return render(request, "accounts/profile_edit.html", {
        "form": form,
        "volunteer": volunteer,
        "availabilities": availabilities,
        "skills": skills,
        "av_form": av_form,
        "av_bulk_form": av_bulk_form,
        "skill_form": skill_form,
        "documents": documents,
        "primary_email": request.user.email,
        "email_addresses": email_addresses,
        "phone_verif": phone_verif,  # <-- pour afficher le bloc OTP
    })

# --------- Notifications ----------
@login_required
def notifications_list(request):
    show = request.GET.get("show", "all")
    qs = Notification.objects.filter(user=request.user).order_by("-created_at")
    if show == "unread":
        qs = qs.filter(is_read=False)

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "accounts/notifications.html", {"page_obj": page_obj, "show": show})


@login_required
def email_change_verify(request, token):
    """Valide un changement d'email à l'aide d'un token envoyé par email.
    Conserve l'ancien email si le token est invalide/expiré.
    """
    ecr = EmailChangeRequest.objects.filter(token=token).first()
    if not ecr or not ecr.is_valid:
        messages.error(request, "Lien de vérification invalide ou expiré.")
        return redirect("benevoles:profile_benevole")
    # Appliquer le nouvel email et synchroniser EmailAddress
    user = ecr.user
    new_email = ecr.new_email
    # Mettre à jour EmailAddress: unique primary + verified
    EmailAddress.objects.filter(user=user).update(primary=False)
    ea, _ = EmailAddress.objects.get_or_create(user=user, email=new_email, defaults={"verified": True, "primary": True})
    if not ea.verified or not ea.primary:
        ea.verified = True
        ea.primary = True
        ea.save(update_fields=["verified", "primary"])
    user.email = new_email
    user.save(update_fields=["email"])
    # Sync volunteer.email too
    try:
        if hasattr(user, "volunteer") and user.volunteer:
            user.volunteer.email = new_email
            user.volunteer.save(update_fields=["email"])
    except Exception:
        pass
    # Sync staff TeamMember email too
    try:
        tm = getattr(user, "team_member", None)
        if tm:
            tm.email = new_email
            if hasattr(tm, "updated_at"):
                tm.save(update_fields=["email", "updated_at"])
            else:
                tm.save()
    except Exception:
        pass
    ecr.used_at = timezone.now()
    ecr.save(update_fields=["used_at"])
    messages.success(request, "Adresse email vérifiée et mise à jour.")
    return redirect("benevoles:profile_benevole")

@login_required
def post_login_redirect(request):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}):
        return redirect(next_url)

    if request.user.is_staff or request.user.is_superuser:
        return redirect("staff:dashboard")

    vol = Volunteer.objects.filter(user=request.user).first()
    if vol:
        return redirect("benevoles:dashboard")

    last_app = (VolunteerApplication.objects
                .filter(user=request.user).order_by("-submitted_at").first())
    if last_app:
        if last_app.status in [ApplicationStatus.PENDING, ApplicationStatus.NEEDS_CHANGES]:
            return redirect("benevoles:application_detail", pk=last_app.pk)

    # Démarrer la candidature si rien n’existe
    return redirect("staff:application_start")

