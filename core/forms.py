from decimal import Decimal, ROUND_HALF_UP
from django import forms
from .models import Donation, ContactMessage
from core.models import TeamMember


class TeamMemberSelfForm(forms.ModelForm):
    """Fiche de complétion Staff simplifiée (contexte santé mentale/social).

    - Supprime les champs non pertinents (github, twitter, site personnel)
    - Pré-remplit le téléphone depuis le profil bénévole s'il existe
    - Laisse la possibilité de modifier toutes les valeurs
    """

    class Meta:
        model = TeamMember
        fields = [
            "bio", "image", "phone", "linkedin",
            "pronouns", "location", "languages", "expertise",
        ]
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Style de base
        for name, f in self.fields.items():
            if getattr(f.widget, "input_type", "") != "checkbox":
                f.widget.attrs.setdefault("class", "w-full mt-1 px-3 py-2 border rounded-lg")

        # Placeholders utiles
        self.fields.get("phone").widget.attrs.setdefault("placeholder", "+243 810 000 000")
        self.fields.get("linkedin").widget.attrs.setdefault("placeholder", "https://www.linkedin.com/in/votre-profil")
        self.fields.get("location").widget.attrs.setdefault("placeholder", "Ville, Pays")
        self.fields.get("languages").widget.attrs.setdefault("placeholder", "fr, en …")
        self.fields.get("expertise").widget.attrs.setdefault("placeholder", "Ex: psychologue, travail social, coordination …")

        # Pré-remplir le téléphone depuis le profil bénévole si présent et si non lié
        try:
            if not self.is_bound:  # seulement sur affichage initial
                inst = getattr(self, "instance", None)
                current = getattr(inst, "phone", "") if inst else ""
                if (not current) and inst and getattr(inst, "user", None):
                    vol = getattr(inst.user, "volunteer", None)
                    if vol and getattr(vol, "phone", ""):
                        self.fields["phone"].initial = vol.phone
        except Exception:
            # silencieux: on n'empêche jamais le formulaire de s'afficher
            pass

class DonationForm(forms.ModelForm):
    # On override le champ pour contrôler précisément la validation et la localisation
    
    amount = forms.DecimalField(
        
        label="Montant (€)",
        min_value=Decimal("1.00"),
        max_digits=10,
        decimal_places=2,
        localize=True,  # autorise les formats locaux (ex: 20,50)
        error_messages={
            "min_value": "Le montant doit être supérieur à 0 €.",
            "invalid": "Veuillez saisir un nombre valide (ex. 20 ou 20,00).",
            "max_digits": "Montant trop grand.",
        },
        widget=forms.NumberInput(
            attrs={
                "class": "w-full rounded-lg border-gray-300 focus:ring-blue-500 focus:border-blue-500",
                "min": "1",
                "step": "0.01",
                "placeholder": "Ex: 20.00",
                "inputmode": "decimal",
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = Donation
        fields = ["donor_name", "amount", "message"]
        labels = {
            "donor_name": "Nom (optionnel)",
            "message": "Message (optionnel)",
        }
        widgets = {
            "donor_name": forms.TextInput(
                attrs={
                    "class": "w-full rounded-lg border-gray-300 focus:ring-blue-500 focus:border-blue-500",
                    "placeholder": "Ex: Marie Dupont",
                    "autocomplete": "name",
                }
            ),
            "message": forms.Textarea(
                attrs={
                    "class": "w-full rounded-lg border-gray-300 focus:ring-blue-500 focus:border-blue-500",
                    "rows": 4,
                    "placeholder": "Un petit mot (optionnel)…",
                }
            ),
        }

    def clean_donor_name(self):
        name = self.cleaned_data.get("donor_name", "") or ""
        # Trim + compresser les espaces internes
        name = " ".join(name.strip().split())
        return name or None

    def clean_amount(self):
        """
        - Accepte 20,50 ou 20.50
        - Implique min à 1.00 €
        - Quantifie à 2 décimales (0.01)
        """
        val = self.cleaned_data.get("amount")

        # Si la localisation n'a pas interprété la virgule, on tente un fallback
        if val is None:
            raw = self.data.get(self.add_prefix("amount"))
            if raw:
                try:
                    raw = raw.replace(",", ".")
                    val = Decimal(raw)
                except Exception:
                    raise forms.ValidationError("Veuillez saisir un nombre valide (ex. 20 ou 20,00).")

        if val is None:
            raise forms.ValidationError("Le montant est requis.")

        if val <= 0:
            raise forms.ValidationError("Le montant doit être supérieur à 0 €.")
        if val < Decimal("1.00"):
            raise forms.ValidationError("Le montant minimum est de 1 €.")

        # Quantification à 2 décimales
        val = val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return val


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "email", "subject", "message"]
        labels = {
            "name": "Nom",
            "email": "Email",
            "subject": "Sujet",
            "message": "Message",
        }
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "mt-1 block w-full border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500",
                "placeholder": "Votre nom",
                "autocomplete": "name",
            }),
            "email": forms.EmailInput(attrs={
                "class": "mt-1 block w-full border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500",
                "placeholder": "vous@exemple.com",
                "autocomplete": "email",
            }),
            "subject": forms.TextInput(attrs={
                "class": "mt-1 block w-full border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500",
                "placeholder": "Sujet du message",
            }),
            "message": forms.Textarea(attrs={
                "class": "mt-1 block w-full border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500",
                "rows": 5,
                "placeholder": "Votre message…",
            }),
        }

    def clean_message(self):
        msg = (self.cleaned_data.get("message") or "").strip()
        if len(msg) < 10:
            raise forms.ValidationError("Merci de détailler un peu votre message (≥ 10 caractères).")
        return msg
