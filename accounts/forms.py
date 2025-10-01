# accounts/forms.py
from decimal import Decimal, InvalidOperation
from typing import Optional
from core.models import City

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import Volunteer, HoursEntry, Availability, VolunteerSkill, Skill
from staff.models import Mission, MissionSignup, VolunteerApplication  # VolunteerApplication utilisé ailleurs
from django.db.models import Q
from django.db.models import DateField as DJDateField, DateTimeField as DJDateTimeField
from django.utils import timezone
# ====================== Utils ======================

def validate_file_size(f, max_mb: int = 10):
    if f and f.size > max_mb * 1024 * 1024:
        raise ValidationError(f"Le fichier dépasse {max_mb} Mo.")

# ====================== Tailwind helpers (light/dark) ======================

TW_INPUT = (
    "w-full mt-1 rounded-lg border border-slate-300 dark:border-slate-700 "
    "bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 "
    "placeholder-slate-400 dark:placeholder-slate-500 "
    "ring-1 ring-inset ring-slate-200 dark:ring-slate-800 "
    "focus:ring-2 focus:ring-blue-500 focus:border-blue-500 focus:outline-none "
    "transition"
)
TW_SELECT = TW_INPUT
TW_TEXTAREA = TW_INPUT + " resize-y"
TW_FILE = (
    "block w-full text-sm text-slate-900 dark:text-slate-100 "
    "file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:font-semibold "
    "file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 "
    "dark:file:bg-slate-800 dark:file:text-slate-100 dark:hover:file:bg-slate-700/80"
)
TW_CHECKBOX_GROUP = (
    "grid grid-cols-2 sm:grid-cols-3 gap-2 p-3 rounded-xl "
    "border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950"
)
TW_ERROR = "border-red-500 ring-red-500 focus:ring-red-500 focus:border-red-500"


def _append_class(widget: forms.Widget, cls: str):
    existing = widget.attrs.get("class", "")
    widget.attrs["class"] = (existing + " " + cls).strip()


class TailwindStyleMixin:
    """Applique les classes Tailwind aux widgets + surbrillance erreurs."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            w = field.widget
            if isinstance(w, (forms.TextInput, forms.EmailInput, forms.URLInput, forms.NumberInput, forms.PasswordInput)):
                _append_class(w, TW_INPUT)
            elif isinstance(w, forms.Textarea):
                _append_class(w, TW_TEXTAREA)
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                _append_class(w, TW_SELECT)
            elif isinstance(w, forms.ClearableFileInput):
                _append_class(w, TW_FILE)
            elif isinstance(w, forms.CheckboxSelectMultiple):
                _append_class(w, TW_CHECKBOX_GROUP)

        # Champs en erreur
        for name in self.errors:
            try:
                _append_class(self.fields[name].widget, TW_ERROR)
            except KeyError:
                pass

# ====================== Profil bénévole ======================
# accounts/forms.py
from django import forms
from django.core.exceptions import ValidationError
import re

from .models import Volunteer, Availability

PHONE_RE = re.compile(r"^\+?\d{8,15}$")

def normalize_phone(value: str) -> str:
    if not value:
        return ""
    v = re.sub(r"[^\d+]", "", value)  # garde chiffres et +
    # corrige 00xx -> +xx
    if v.startswith("00"):
        v = "+" + v[2:]
    return v

class VolunteerForm(forms.ModelForm):
    # ré-auth obligatoire
    confirm_password = forms.CharField(
        required=True,
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={
            "autocomplete": "current-password",
            "placeholder": "Re-saisir votre mot de passe",
        }),
        help_text="Par sécurité, veuillez confirmer votre mot de passe pour enregistrer.",
    )

    # case à cocher pour supprimer l'avatar (si tu l’utilises déjà)
    remove_avatar = forms.BooleanField(required=False, label="Supprimer la photo actuelle")

    # --- ADD: Localisation ---
    city = forms.ModelChoiceField(
        label="Ville (RDC)",
        queryset=City.objects.filter(country_code="CD").order_by("name"),
        required=True,                    # mets False si tu veux laisser facultatif
        empty_label="— Choisir une ville —",
        widget=forms.Select()
    )
    class Meta:
        model = Volunteer
        fields = ["name", "email", "phone", "motivation", "avatar", "city"]  # name sera verrouillé

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["name"].disabled = True
        self.fields["name"].help_text = "Le nom du compte ne peut pas être modifié."

        for f in self.fields.values():
            css = f.widget.attrs.get("class", "")
            f.widget.attrs["class"] = (css + " w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2").strip()

        # (optionnel) prioriser Kinshasa tout en haut si tu veux
        #self.fields["city"].queryset = self.fields["city"].queryset.order_by(
         #   models.Case(models.When(name="Kinshasa", then=0), default=1), "name"
        #)
    def clean_name(self):
        # Même si le champ est disabled, on re-vérifie côté serveur
        orig = self.instance.name or ""
        val = self.cleaned_data.get("name", orig)
        if val != orig:
            raise ValidationError("Le nom du compte ne peut pas être modifié.")
        return orig

    def clean_confirm_password(self):
        pwd = self.cleaned_data.get("confirm_password") or ""
        if not self.user or not self.user.check_password(pwd):
            raise ValidationError("Mot de passe incorrect.")
        return pwd

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if not phone:
            return ""
        phone_norm = normalize_phone(phone)
        if not PHONE_RE.match(phone_norm):
            raise ValidationError("Numéro invalide. Utilisez le format international (+337... ou +243...).")
        return phone_norm

    def save(self, commit=True):
        obj = super().save(commit=False)
        # gestion suppression avatar
        if self.cleaned_data.get("remove_avatar") and obj.avatar:
            obj.avatar.delete(save=False)
            obj.avatar = None
        if commit:
            obj.save()
            self.save_m2m()
        return obj


# ====================== Disponibilités & Compétences ======================

# accounts/forms.py
from django import forms
from .models import Availability

class AvailabilityAddForm(forms.ModelForm):
    class Meta:
        model = Availability
        fields = ["day", "slot"]  # on ne montre pas 'volunteer' dans le form

    def __init__(self, *args, volunteer=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.volunteer = volunteer  # <-- indispensable pour clean/save

    def clean(self):
        cleaned = super().clean()
        vol = getattr(self, "volunteer", None)
        if not vol:
            # On lève une ValidationError (pas un AttributeError) pour remonter proprement à l'UI
            raise forms.ValidationError("Contexte bénévole manquant. Veuillez recharger la page et réessayer.")

        day = cleaned.get("day")
        slot = cleaned.get("slot")
        if day is None or not slot:
            return cleaned

        # Unicité (mirror du unique_together du modèle)
        exists = Availability.objects.filter(
            volunteer=vol, day=day, slot=slot
        ).exists()
        if exists:
            raise forms.ValidationError("Cette disponibilité existe déjà.")

        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        # attacher le bénévole ici, même si la vue le fait déjà, pour robustesse
        if self.volunteer and not getattr(obj, "volunteer_id", None):
            obj.volunteer = self.volunteer
        if commit:
            obj.save()
        return obj


class VolunteerSkillAddForm(TailwindStyleMixin, forms.ModelForm):
    new_skill_name = forms.CharField(
        label="Nouvelle compétence",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ex: Premiers secours"}),
        help_text="Choisissez une compétence existante ou créez-en une nouvelle.",
    )
    proof = forms.FileField(required=False, label="Preuve (facultatif)", widget=forms.ClearableFileInput())

    class Meta:
        model = VolunteerSkill
        fields = ["skill", "level", "proof"]
        labels = {"skill": "Compétence", "level": "Niveau"}
        widgets = {"skill": forms.Select(), "level": forms.Select()}

    def __init__(self, *args, volunteer: Optional[Volunteer] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.volunteer = volunteer
        self.fields["skill"].required = False  # si on saisit new_skill_name

    def clean(self):
        cleaned = super().clean()
        skill = cleaned.get("skill")
        new_name = (self.cleaned_data.get("new_skill_name") or "").strip()
        if not skill and not new_name:
            raise forms.ValidationError("Choisissez une compétence OU saisissez un nom de nouvelle compétence.")
        return cleaned

    def save(self, commit=True):
        vol = self.volunteer
        skill = self.cleaned_data.get("skill")
        new_name = (self.cleaned_data.get("new_skill_name") or "").strip()
        if not skill and new_name:
            skill, _ = Skill.objects.get_or_create(name=new_name)
        obj = VolunteerSkill(
            volunteer=vol,
            skill=skill,
            level=self.cleaned_data["level"],
            proof=self.cleaned_data.get("proof"),
        )
        if commit:
            obj.save()
        return obj


class AvailabilityBulkForm(TailwindStyleMixin, forms.Form):
    days = forms.MultipleChoiceField(
        label="Jours",
        choices=Availability.Day.choices,
        widget=forms.CheckboxSelectMultiple(attrs={"class": TW_CHECKBOX_GROUP}),
        required=True,
    )
    slots = forms.MultipleChoiceField(
        label="Créneaux",
        choices=Availability.Slot.choices,
        widget=forms.CheckboxSelectMultiple(attrs={"class": TW_CHECKBOX_GROUP}),
        required=True,
    )

# ====================== Déclaration d’heures ======================
class HoursEntryForm(forms.ModelForm):
    proof = forms.FileField(
        required=True,
        label="Justificatif (photo/PDF)",
        help_text="Ajoutez une image ou un PDF comme preuve."
    )

    class Meta:
        model = HoursEntry
        # ⚠️ On NE demande plus 'date' côté UI
        fields = ["hours", "mission", "note"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["mission"].required = True

        # --- N'afficher que les missions ACCEPTÉES + publiées + TERMINÉES ---
        now = timezone.now()
        today = timezone.localdate()

        ended_q = Q()
        try:
            ef = Mission._meta.get_field("end_date")
        except Exception:
            ef = None
        try:
            sf = Mission._meta.get_field("start_date")
        except Exception:
            sf = None

        if ef:
            # fin <= maintenant (ou aujourd'hui si DateField)
            if isinstance(ef, DJDateTimeField):
                ended_q |= Q(end_date__lte=now)
            else:
                ended_q |= Q(end_date__lte=today)
            ended_q &= Q(end_date__isnull=False)
        elif sf:
            # fallback: début strictement avant aujourd'hui
            if isinstance(sf, DJDateTimeField):
                ended_q |= Q(start_date__lt=now)
            else:
                ended_q |= Q(start_date__lt=today)
            ended_q &= Q(start_date__isnull=False)

        if user and hasattr(user, "volunteer"):
            accepted = MissionSignup.Status.ACCEPTED
            qs = (
                Mission.objects
                .filter(
                    signups__volunteer=user.volunteer,
                    signups__status=accepted,
                    status="published",
                )
                .filter(ended_q)
                .distinct()
                .order_by("-end_date", "-start_date", "title")
            )
        else:
            qs = Mission.objects.none()

        self.fields["mission"].queryset = qs
        self.fields["hours"].widget.attrs.update({"step": "0.25", "min": "0", "inputmode": "decimal"})

    # --- Validations ---
    def clean_proof(self):
        uploaded = self.cleaned_data.get("proof")
        if not uploaded:
            raise ValidationError("Le justificatif est obligatoire.")
        # taille/format
        from .forms import validate_file_size  # si ton util est ailleurs, ajuste l'import
        validate_file_size(uploaded, max_mb=10)
        allowed = (".pdf", ".jpg", ".jpeg", ".png", ".webp")
        name = (uploaded.name or "").lower()
        if not any(name.endswith(ext) for ext in allowed):
            raise ValidationError("Formats acceptés : PDF, JPG, PNG, WEBP.")
        return uploaded

    def clean_hours(self):
        raw = self.data.get(self.add_prefix("hours"), "")
        if isinstance(raw, str) and "," in raw:
            raw = raw.replace(",", ".")
        try:
            val = Decimal(str(raw))
        except (InvalidOperation, TypeError):
            raise ValidationError("Entrez un nombre valide (ex : 1.5 pour 1h30).")
        if val <= 0:
            raise ValidationError("Le nombre d’heures doit être strictement positif.")
        return val

    def clean(self):
        cleaned = super().clean()
        mission = cleaned.get("mission")

        if not mission:
            self.add_error("mission", "Choisissez une mission acceptée.")
            return cleaned

        # sécurité: la mission doit être bien ACCEPTÉE pour cet utilisateur
        ok = MissionSignup.objects.filter(
            mission=mission,
            volunteer__user=self.user,
            status=MissionSignup.Status.ACCEPTED
        ).exists()
        if not ok:
            self.add_error("mission", "Vous ne pouvez déclarer des heures que sur une mission acceptée.")

        return cleaned

    def save(self, commit=True):
        """
        Fixe automatiquement la date :
        - fin de mission si elle existe,
        - sinon début de mission,
        - sinon aujourd’hui (sécurité).
        """
        entry = super().save(commit=False)
        mission = self.cleaned_data.get("mission")

        def _to_date(val):
            if val is None:
                return None
            try:
                return val.date()  # si DateTime
            except AttributeError:
                return val          # déjà une date

        mdate = None
        if mission is not None:
            mdate = mission.end_date or mission.start_date
            mdate = _to_date(mdate)

        from django.utils import timezone
        entry.date = mdate or timezone.localdate()

        if commit:
            entry.save()
        return entry
# ====================== Allauth: reset + signup (terms) ======================

from allauth.account.forms import ResetPasswordForm, SignupForm
from allauth.socialaccount.forms import SignupForm as SocialSignupFormBase
from legal.models import LegalDocument, LegalAcceptance

INPUT_CLS = (
    "w-full rounded-xl border border-slate-300 bg-white/80 px-3 py-2.5 "
    "shadow-sm outline-none transition focus:border-blue-500 "
    "focus:ring-4 focus:ring-blue-100 dark:bg-white/10 dark:border-white/10 "
    "dark:focus:ring-blue-500/20"
)

class StyledResetPasswordForm(ResetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget = forms.EmailInput(attrs={
            "class": INPUT_CLS,
            "autocomplete": "email",
            "inputmode": "email",
            "placeholder": "exemple@domaine.fr",
        })


class LegalAcceptanceMixin:
    legal_keys = ("terms", "privacy")
    legal_locale = "fr"

    def __init__(self, *args, **kwargs):
        self._legal_docs_cache = None
        super().__init__(*args, **kwargs)

    def _current_legal_documents(self):
        if self._legal_docs_cache is not None:
            return self._legal_docs_cache

        docs = []
        missing = []
        for key in self.legal_keys:
            try:
                document = LegalDocument.objects.get(key=key, locale=self.legal_locale)
            except LegalDocument.DoesNotExist:
                missing.append(key)
                continue
            version = document.current_version()
            if not version:
                missing.append(key)
                continue
            docs.append((document, version))

        if missing:
            raise forms.ValidationError(
                _("Les documents légaux requis sont indisponibles. Merci de réessayer plus tard."),
                code="legal_unavailable",
            )

        self._legal_docs_cache = docs
        return docs

    def _record_legal_acceptance(self, user, request):
        if not user or request is None:
            return

        try:
            docs = self._current_legal_documents()
        except forms.ValidationError:
            return

        xff = request.META.get("HTTP_X_FORWARDED_FOR", "") or ""
        ip = xff.split(",")[0].strip() if xff else (request.META.get("REMOTE_ADDR") or None)
        ua = (request.META.get("HTTP_USER_AGENT", "") or "")[:1024]

        for document, version in docs:
            LegalAcceptance.objects.get_or_create(
                user=user,
                version=version,
                defaults={
                    "document": document,
                    "ip": ip,
                    "user_agent": ua,
                },
            )


class TermsSignupForm(LegalAcceptanceMixin, SignupForm):
    accept_terms = forms.BooleanField(
        label=_("J'accepte les conditions d'utilisation et la politique de confidentialite"),
        required=True,
        error_messages={
            "required": _("Vous devez accepter les conditions d'utilisation et la politique de confidentialite."),
        },
    )

    def clean_accept_terms(self):
        accepted = self.cleaned_data.get("accept_terms")
        if not accepted:
            raise forms.ValidationError(
                _("Vous devez accepter les conditions d'utilisation et la politique de confidentialite."),
                code="required",
            )
        self._current_legal_documents()
        return accepted

    def save(self, request):
        user = super().save(request)
        self._record_legal_acceptance(user, request)
        return user


class TermsSocialSignupForm(LegalAcceptanceMixin, SocialSignupFormBase):
    accept_terms = forms.BooleanField(
        label=_("J'accepte les conditions d'utilisation et la politique de confidentialite"),
        required=True,
        error_messages={
            "required": _("Vous devez accepter les conditions d'utilisation et la politique de confidentialite."),
        },
    )

    def clean_accept_terms(self):
        accepted = self.cleaned_data.get("accept_terms")
        if not accepted:
            raise forms.ValidationError(
                _("Vous devez accepter les conditions d'utilisation et la politique de confidentialite."),
                code="required",
            )
        self._current_legal_documents()
        return accepted

    def save(self, request, sociallogin):
        user = super().save(request, sociallogin)
        self._record_legal_acceptance(user, request)
        return user

# ====================== Wizard d’inscription bénévole (exemple) ======================

class ProfileStepForm(forms.Form):
    full_name = forms.CharField(label="Nom complet", max_length=150)
    phone = forms.CharField(label="Téléphone", max_length=50)
    birthdate = forms.DateField(label="Date de naissance", widget=forms.DateInput(attrs={"type": "date"}))
    address = forms.CharField(label="Adresse", max_length=255)

    city = forms.ModelChoiceField(
        label="Ville (RDC)",
        queryset=City.objects.filter(country_code="CD").order_by("name"),
        required=True,
        empty_label="— Choisir une ville —",
        widget=forms.Select()
    )

class DocumentsStepForm(forms.Form):
    id_type = forms.ChoiceField(
        label="Pièce d'identité",
        choices=[("id", "CNI"), ("passport", "Passeport"), ("residence", "Titre de séjour")]
    )
    id_number = forms.CharField(label="Numéro de document", max_length=120)
    has_cv = forms.BooleanField(label="J'ai un CV (optionnel)", required=False)
    motivation = forms.CharField(label="Motivation", widget=forms.Textarea)

class AvailabilityStepForm(forms.Form):
    weekdays = forms.MultipleChoiceField(
        label="Disponibilités (semaine)",
        widget=forms.CheckboxSelectMultiple,
        choices=[("mon", "Lundi"), ("tue", "Mardi"), ("wed", "Mercredi"), ("thu", "Jeudi"), ("fri", "Vendredi")],
        required=False,
    )
    weekends = forms.MultipleChoiceField(
        label="Disponibilités (week-end)",
        widget=forms.CheckboxSelectMultiple,
        choices=[("sat", "Samedi"), ("sun", "Dimanche")],
        required=False,
    )

class SkillsStepForm(forms.Form):
    skills = forms.CharField(label="Compétences (libre)", widget=forms.Textarea,
                             help_text="Ex.: accueil, logistique, communication…")
    notes = forms.CharField(label="Autres infos", widget=forms.Textarea, required=False)

STEP_FORMS = [ProfileStepForm, DocumentsStepForm, AvailabilityStepForm, SkillsStepForm]
STEP_KEYS  = ["profile", "documents", "availability", "skills"]

assert len(STEP_FORMS) == len(STEP_KEYS)
