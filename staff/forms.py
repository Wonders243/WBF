# staff/forms.py
from django import forms
from django.forms import ClearableFileInput
from .models import Mission
from accounts.models import Availability
from core.models import Event, Project, TeamMember, Partenaire, News, Testimonial, EducationStory
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.forms import modelformset_factory
from .models import VolunteerApplication, VolunteerApplicationDocument

User = get_user_model()


# -------------------------------------------------------------------
# Styles réutilisables
# -------------------------------------------------------------------
BASE_INPUT = (
    "w-full px-3 py-2 rounded-lg border "
    "border-slate-300 dark:border-white/10 "
    "bg-white dark:bg-slate-950 "
    "text-slate-900 dark:text-slate-100 "
    "placeholder-slate-400 "
    "focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
)

FILE_INPUT = (
    "block w-full text-sm rounded-lg border "
    "border-slate-300 dark:border-white/10 "
    "focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 "
    "file:mr-3 file:py-2.5 file:px-4 file:rounded-lg file:border-0 "
    "file:bg-slate-100 file:text-slate-900 "
    "dark:file:bg-slate-800 dark:file:text-slate-100"
)

# -------------------------------------------------------------------
# Projets
# -------------------------------------------------------------------
class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["title", "description", "partners", "image", "link"]
        widgets = {
            "title":        forms.TextInput(attrs={"class": BASE_INPUT}),
            "description":  forms.Textarea(attrs={"rows": 6, "class": BASE_INPUT}),
            "partners":     forms.SelectMultiple(attrs={"class": BASE_INPUT}),
            "image":        ClearableFileInput(attrs={"class": FILE_INPUT, "accept": "image/*"}),
            "link":         forms.URLInput(attrs={"class": BASE_INPUT, "placeholder": "https://…"}),
        }

    def clean_image(self):
        f = self.cleaned_data.get("image")
        if not f:
            return f
        max_mb = 5
        if f.size > max_mb * 1024 * 1024:
            raise forms.ValidationError(f"Image trop volumineuse (>{max_mb} Mo).")
        content_type = getattr(f, "content_type", "") or ""
        if not content_type.startswith("image/"):
            raise forms.ValidationError("Fichier non valide : une image est requise.")
        return f

# -------------------------------------------------------------------
# Missions
# -------------------------------------------------------------------
class MissionForm(forms.ModelForm):
    class Meta:
        model = Mission
        fields = [
            "title", "description", "location",
            "event", "start_date", "end_date",
            "capacity", "status",
        ]
        widgets = {
            "title":       forms.TextInput(attrs={"class": BASE_INPUT}),
            "location":    forms.TextInput(attrs={"class": BASE_INPUT}),
            "description": forms.Textarea(attrs={"class": BASE_INPUT, "rows": 6}),
            "event":       forms.Select(attrs={"class": BASE_INPUT}),
            "start_date":  forms.DateTimeInput(attrs={"type": "datetime-local", "class": BASE_INPUT}),
            "end_date":    forms.DateTimeInput(attrs={"type": "datetime-local", "class": BASE_INPUT}),
            "capacity":    forms.NumberInput(attrs={"class": BASE_INPUT, "min": 0}),
            "status":      forms.Select(attrs={"class": BASE_INPUT}),
        }

# -------------------------------------------------------------------
# Filtres d'invitation
# -------------------------------------------------------------------
class InviteFilterForm(forms.Form):
    q = forms.CharField(label="Recherche", required=False)
    skill = forms.CharField(label="Compétence", required=False)
    day = forms.ChoiceField(label="Jour", required=False, choices=[])
    slot = forms.ChoiceField(label="Créneau", required=False, choices=[])
    only_available = forms.BooleanField(
        label="Masquer ceux déjà invités / en attente / acceptés",
        required=False,
        initial=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Choices dynamiques
        days = Availability.objects.order_by().values_list("day", flat=True).distinct()
        slots = Availability.objects.order_by().values_list("slot", flat=True).distinct()
        self.fields["day"].choices = [("", "— Jour —")] + [(d, str(d).title()) for d in days if d]
        self.fields["slot"].choices = [("", "— Créneau —")] + [(s, str(s).title()) for s in slots if s]

        # Styles dark mode
        self.fields["q"].widget.attrs.update({"class": BASE_INPUT, "placeholder": "Nom, email, téléphone…"})
        self.fields["skill"].widget.attrs.update({"class": BASE_INPUT, "placeholder": "Compétence (ex: Python, Permis B)"})
        self.fields["day"].widget.attrs.update({"class": BASE_INPUT})
        self.fields["slot"].widget.attrs.update({"class": BASE_INPUT})
        self.fields["only_available"].widget.attrs.update({"class": "h-4 w-4 align-middle"})

# -------------------------------------------------------------------
# Formulaire bulk d’invitations
# -------------------------------------------------------------------
class BulkInviteForm(forms.Form):
    volunteer_ids = forms.MultipleChoiceField(widget=forms.MultipleHiddenInput)
    note = forms.CharField(
        label="Message (optionnel)",
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 3, "class": BASE_INPUT, "placeholder": "Ex: Besoin d’aide samedi de 9h à 12h…"}
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # les choices seront injectées dans la vue selon la page courante
        self.fields["volunteer_ids"].choices = []

# -------------------------------------------------------------------
# Événements
# -------------------------------------------------------------------
class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ["title", "date", "location", "description", "image", "projects"]
        widgets = {
            "title":       forms.TextInput(attrs={"class": BASE_INPUT}),
            "date":        forms.DateInput(attrs={"type": "date", "class": BASE_INPUT}),
            "location":    forms.TextInput(attrs={"class": BASE_INPUT}),
            "description": forms.Textarea(attrs={"rows": 6, "class": BASE_INPUT}),
            "projects":    forms.SelectMultiple(attrs={"class": BASE_INPUT}),
            "image":       ClearableFileInput(attrs={"class": FILE_INPUT}),
        }

# -------------------------------------------------------------------
# Team Member & Partenaire (déjà dark via BASE_INPUT)
# -------------------------------------------------------------------

class TeamMemberForm(forms.ModelForm):
    class Meta:
        model = TeamMember
        fields = [
            "user",
            "name", "role", "seniority", "department", "bio", "image",
            "email", "phone", "website", "linkedin", "twitter", "github",
            "pronouns", "location", "languages", "expertise",
            "is_active", "sort_order", "joined_on", "left_on",
        ]
        widgets = {
            "joined_on": forms.DateInput(attrs={"type": "date"}),
            "left_on": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        inst = getattr(self, "instance", None)
        current_user_id = inst.user_id if inst and inst.pk else None

        # Users actifs non liés, + le user déjà lié si édition
        self.fields["user"].required = False
        self.fields["user"].queryset = User.objects.filter(is_active=True).filter(
            Q(team_member__isnull=True) | Q(pk=current_user_id)
        ).order_by("username")

        # Style
        for name, f in self.fields.items():
            if getattr(f.widget, "input_type", "") != "checkbox":
                f.widget.attrs.setdefault("class", "w-full mt-1 px-3 py-2 border rounded-lg")

        # Verrou visuel si un user est déjà lié (édition)
        if current_user_id:
            self._lock_name_email()

        # Si on a un user choisi dans la requête (POST/GET), on peut marquer readonly côté affichage
        # NB: l’auto-remplissage JS assurera la mise à jour live ; de toute façon on reforce au clean().
        sel_user_id = (self.data.get("user") or "").strip()
        if sel_user_id:
            self._lock_name_email()

    def _lock_name_email(self):
        # readonly (et non disabled) pour que la valeur reste envoyée au POST
        for fld in ("name", "email"):
            w = self.fields[fld].widget
            w.attrs["readonly"] = "readonly"
            w.attrs["aria-readonly"] = "true"
            # petit plus visuel (optionnel)
            cls = w.attrs.get("class", "")
            w.attrs["class"] = (cls + " bg-slate-50 dark:bg-slate-800 cursor-not-allowed").strip()
            w.attrs["title"] = "Synchronisé avec le compte utilisateur"

    def clean(self):
        cleaned = super().clean()
        user = cleaned.get("user")

        # Cohérence user unique
        if user:
            other_exists = TeamMember.objects.filter(user=user).exclude(pk=self.instance.pk).exists()
            if other_exists:
                self.add_error("user", "Cet utilisateur est déjà lié à un autre membre de l'équipe.")

            # 🔒 Verrou métier : si user est lié, on écrase name/email depuis User
            full = (user.get_full_name() or "").strip() or user.get_username()
            cleaned["name"] = full
            cleaned["email"] = user.email or ""

        # Dates cohérentes
        j, l = cleaned.get("joined_on"), cleaned.get("left_on")
        if j and l and l < j:
            self.add_error("left_on", "La date de départ ne peut pas être antérieure à la date d’arrivée.")

        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        # Double sécurité serveur (au cas où) : resynchroniser avant save
        if obj.user_id:
            obj.apply_user_sync()
        if commit:
            obj.save()
            self.save_m2m()
        return obj

class PartenaireForm(forms.ModelForm):
    class Meta:
        model = Partenaire
        fields = [
            "name", "category", "tier", "description", "logo", "website",
            "contact_name", "contact_email", "contact_phone",
            "address", "linkedin", "twitter", "facebook", "instagram",
            "start_date", "end_date", "contribution",
            "is_active", "sort_order",
        ]
        widgets = {
            "name":          forms.TextInput(attrs={"class": BASE_INPUT}),
            "category":      forms.Select(attrs={"class": BASE_INPUT}),
            "tier":          forms.Select(attrs={"class": BASE_INPUT}),
            "description":   forms.Textarea(attrs={"rows": 6, "class": BASE_INPUT}),
            "logo":          forms.ClearableFileInput(attrs={"class": "block w-full text-sm"}),
            "website":       forms.URLInput(attrs={"class": BASE_INPUT}),
            "contact_name":  forms.TextInput(attrs={"class": BASE_INPUT}),
            "contact_email": forms.EmailInput(attrs={"class": BASE_INPUT}),
            "contact_phone": forms.TextInput(attrs={"class": BASE_INPUT}),
            "address":       forms.Textarea(attrs={"rows": 3, "class": BASE_INPUT}),
            "linkedin":      forms.URLInput(attrs={"class": BASE_INPUT}),
            "twitter":       forms.URLInput(attrs={"class": BASE_INPUT}),
            "facebook":      forms.URLInput(attrs={"class": BASE_INPUT}),
            "instagram":     forms.URLInput(attrs={"class": BASE_INPUT}),
            "start_date":    forms.DateInput(attrs={"type": "date", "class": BASE_INPUT}),
            "end_date":      forms.DateInput(attrs={"type": "date", "class": BASE_INPUT}),
            "contribution":  forms.Textarea(attrs={"rows": 3, "class": BASE_INPUT}),
            "is_active":     forms.CheckboxInput(attrs={"class": "h-4 w-4"}),
            "sort_order":    forms.NumberInput(attrs={"class": BASE_INPUT, "min": 0}),
        }

# -------------------------------------------------------------------
# Actualités / Témoignages / Histoires
# -------------------------------------------------------------------
class NewsForm(forms.ModelForm):
    class Meta:
        model = News
        fields = ["title", "content", "image"]
        widgets = {
            "title":   forms.TextInput(attrs={"class": BASE_INPUT}),
            "content": forms.Textarea(attrs={"class": BASE_INPUT, "rows": 8}),
            "image":   ClearableFileInput(attrs={"class": FILE_INPUT, "accept": "image/*"}),
        }

    def clean_image(self):
        f = self.cleaned_data.get("image")
        if not f:
            return f
        max_mb = 5
        if getattr(f, "size", 0) > max_mb * 1024 * 1024:
            raise forms.ValidationError(f"Image trop volumineuse (>{max_mb} Mo).")
        ct = getattr(f, "content_type", "") or ""
        if not ct.startswith("image/"):
            raise forms.ValidationError("Fichier non valide : une image est requise.")
        return f

class TestimonialForm(forms.ModelForm):
    class Meta:
        model = Testimonial
        fields = ["author", "content", "image"]
        widgets = {
            "author":  forms.TextInput(attrs={"class": BASE_INPUT}),
            "content": forms.Textarea(attrs={"class": BASE_INPUT, "rows": 6}),
            "image":   ClearableFileInput(attrs={"class": FILE_INPUT, "accept": "image/*"}),
        }

    def clean_image(self):
        f = self.cleaned_data.get("image")
        if not f:
            return f
        max_mb = 5
        if getattr(f, "size", 0) > max_mb * 1024 * 1024:
            raise forms.ValidationError(f"Image trop volumineuse (>{max_mb} Mo).")
        ct = getattr(f, "content_type", "") or ""
        if not ct.startswith("image/"):
            raise forms.ValidationError("Fichier non valide : une image est requise.")
        return f

class EducationStoryForm(forms.ModelForm):
    class Meta:
        model = EducationStory
        fields = ["title", "category", "beneficiary_name", "city", "cover", "consent_file", "quote", "is_published"]
        widgets = {
            "title":            forms.TextInput(attrs={"class": BASE_INPUT}),
            "category":         forms.Select(attrs={"class": BASE_INPUT}),
            "beneficiary_name": forms.TextInput(attrs={"class": BASE_INPUT}),
            "city":             forms.Select(attrs={"class": BASE_INPUT}),
            "cover":            ClearableFileInput(attrs={"class": FILE_INPUT, "accept": "image/*"}),
            "consent_file":     ClearableFileInput(attrs={"class": FILE_INPUT, "accept": "application/pdf,image/*"}),
            "quote":            forms.Textarea(attrs={"class": BASE_INPUT, "rows": 4}),
            "is_published":     forms.CheckboxInput(attrs={"class": "h-4 w-4"}),
        }

    def clean_cover(self):
        f = self.cleaned_data.get("cover")
        if not f:
            return f
        max_mb = 5
        if getattr(f, "size", 0) > max_mb * 1024 * 1024:
            raise forms.ValidationError(f"Image de couverture trop volumineuse (>{max_mb} Mo).")
        ct = getattr(f, "content_type", "") or ""
        if not ct.startswith("image/"):
            raise forms.ValidationError("Fichier non valide : une image est requise.")
        return f

    def clean_consent_file(self):
        f = self.cleaned_data.get("consent_file")
        if not f:
            return f
        max_mb = 8
        if getattr(f, "size", 0) > max_mb * 1024 * 1024:
            raise forms.ValidationError(f"Fichier trop volumineux (>{max_mb} Mo).")
        # Autoriser PDF et images
        ct = getattr(f, "content_type", "") or ""
        if not (ct == "application/pdf" or ct.startswith("image/")):
            raise forms.ValidationError("Type non autorisé (PDF ou image requis).")
        return f

# benevoles/forms.py
from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from .models import VolunteerApplication, VolunteerApplicationDocument  # ajuste l'import si besoin

class TailwindFormMixin:
    base_css = ("block w-full rounded-lg border border-slate-300 bg-white/90 px-3 py-2 text-sm "
                "shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 "
                "dark:bg-slate-900 dark:border-slate-700 dark:text-slate-100")
    textarea_css = base_css + " min-h-[120px]"
    select_css = base_css

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Appliquer classes + placeholders utiles
        placeholders = {
            "full_name": "Nom et prénom",
            "phone": "Ex. +33 6 12 34 56 78",
            "address_line1": "N° et rue",
            "address_line2": "Bâtiment, étage… (optionnel)",
            "city": "Ville",
            "state": "Région/État (si applicable)",
            "postal_code": "Code postal",
            "country": "Pays",
            "id_number": "Numéro figurant sur votre pièce",
            "emergency_contact": "Nom & téléphone d’un proche",
            "motivation": "Dites-nous pourquoi vous voulez devenir bénévole…",
        }

        for name, field in self.fields.items():
            w = field.widget
            # Type "tel" pour téléphone, "date" pour dates si ce n’est pas déjà fait
            if name == "phone":
                w.input_type = "tel"
            if name in ("birth_date", "id_expiry") and not isinstance(w, forms.DateInput):
                w = forms.DateInput(attrs={"type": "date"})
                self.fields[name].widget = w

            # Classes Tailwind
            if isinstance(w, forms.Textarea):
                w.attrs["class"] = f"{w.attrs.get('class','')} {self.textarea_css}".strip()
            elif isinstance(w, (forms.Select, forms.SelectMultiple, forms.DateInput)):
                w.attrs["class"] = f"{w.attrs.get('class','')} {self.select_css}".strip()
            else:
                w.attrs["class"] = f"{w.attrs.get('class','')} {self.base_css}".strip()

            # Placeholders
            if name in placeholders and isinstance(w, (forms.TextInput, forms.Textarea)):
                w.attrs.setdefault("placeholder", placeholders[name])

class VolunteerApplicationForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = VolunteerApplication
        fields = [
            # Identité
            "full_name", "phone", "birth_date",
            # Adresse
            "address_line1", "address_line2", "postal_code", "city", "state", "country",
            # Pièce d’identité
            "id_type", "id_number", "id_expiry",
            # Divers
            "emergency_contact", "motivation",
        ]
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}),
            "id_expiry": forms.DateInput(attrs={"type": "date"}),
            "motivation": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {
            "full_name": "Nom complet",
            "phone": "Téléphone",
            "birth_date": "Date de naissance",
            "address_line1": "Adresse (ligne 1)",
            "address_line2": "Complément d’adresse",
            "postal_code": "Code postal",
            "city": "Ville",
            "state": "Région/État",
            "country": "Pays",
            "id_type": "Type de pièce",
            "id_number": "Numéro de la pièce",
            "id_expiry": "Date d’expiration",
            "emergency_contact": "Contact d’urgence",
            "motivation": "Motivation",
        }
        help_texts = {
            "id_type": "Choisissez la pièce que vous allez transmettre.",
            "id_number": "Exactement comme indiqué sur la pièce.",
            "emergency_contact": "Personne à prévenir en cas d’urgence (nom + téléphone).",
        }

    # Petites validations utiles (optionnelles)
    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if len(phone) < 6:
            raise forms.ValidationError("Numéro de téléphone trop court.")
        return phone

    def clean(self):
        cleaned = super().clean()
        # Exemple : si id_type est fourni, exiger id_number
        if cleaned.get("id_type") and not cleaned.get("id_number"):
            self.add_error("id_number", "Le numéro de pièce est requis.")
        return cleaned


class VolunteerApplicationDocumentForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = VolunteerApplicationDocument
        fields = ["doc_type", "file"]
        labels = {"doc_type": "Type de document", "file": "Fichier"}

# Recommandé : inline formset lié à l’application (si VolunteerApplicationDocument a FK -> VolunteerApplication avec related_name='documents')
DocumentFormSet = inlineformset_factory(
    VolunteerApplication,
    VolunteerApplicationDocument,
    form=VolunteerApplicationDocumentForm,
    fields=["doc_type", "file"],
    extra=3,
    can_delete=True,
)
