# staff/views_legal.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django import forms
from django.utils.text import slugify

from legal.models import LegalDocument, LegalVersion

# ─────────────────────────────────────────────────────────────────────────────
# FORMS
# ─────────────────────────────────────────────────────────────────────────────
class LegalDocumentForm(forms.ModelForm):
    class Meta:
        model = LegalDocument
        fields = ["key", "locale", "title", "slug"]

    def clean_slug(self):
        slug = (self.cleaned_data.get("slug") or slugify(self.cleaned_data.get("title") or "")).strip()
        if not slug:
            raise forms.ValidationError("Slug requis (généré depuis le titre si vide)")
        qs = LegalDocument.objects.all()
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        base = slug
        i = 2
        while qs.filter(slug=slug).exists():
            slug = f"{base}-{i}"
            i += 1
        return slug

class LegalVersionForm(forms.ModelForm):
    class Meta:
        model = LegalVersion
        fields = ["version", "status", "effective_date", "body_md", "change_log"]
        widgets = {
            "effective_date": forms.DateInput(attrs={"type": "date"}),
            "body_md": forms.Textarea(attrs={"rows": 24, "class": "font-mono"}),
            "change_log": forms.Textarea(attrs={"rows": 4}),
        }

    def clean(self):
        data = super().clean()
        status = data.get("status")
        version = (data.get("version") or "").strip()
        # Auto-assign version if publishing without one
        if status == "published" and not version:
            today = timezone.localdate().isoformat()
            version = f"v1.0-{today}"
            doc = getattr(self.instance, "document", None)
            if doc:
                base = version
                i = 2
                existing_qs = doc.versions.exclude(pk=getattr(self.instance, "pk", None))
                while existing_qs.filter(version=version).exists():
                    version = f"{base}-{i}"
                    i += 1
            data["version"] = version
            self.cleaned_data["version"] = version
        # Default effective_date to today when publishing without date
        if status == "published" and not data.get("effective_date"):
            data["effective_date"] = timezone.localdate()
            self.cleaned_data["effective_date"] = data["effective_date"]
        return data

# ─────────────────────────────────────────────────────────────────────────────
# LISTE
# ─────────────────────────────────────────────────────────────────────────────
@staff_member_required
def legal_list(request):
    docs = (LegalDocument.objects
            .all()
            .prefetch_related("versions"))
    # Prépare un objet "current" par doc pour l’affichage
    rows = []
    for d in docs:
        current = d.current_version()
        rows.append({"doc": d, "current": current})
    return render(request, "staff/legal_list.html", {"rows": rows})

# ─────────────────────────────────────────────────────────────────────────────
# EDIT / NEW
#   - route "legal_new" : création d’un doc + 1ère version
#   - route "legal_edit/<pk>" : édite le doc + DERNIÈRE version (ou crée une nouvelle si ?new_version=1)
# ─────────────────────────────────────────────────────────────────────────────
@staff_member_required
def legal_edit(request, pk=None):
    doc = get_object_or_404(LegalDocument, pk=pk) if pk else None

    # Choix de la version à éditer :
    ver = None
    if doc:
        if request.GET.get("new_version") == "1":
            ver = LegalVersion(document=doc, version="", status="draft")
        else:
            # édite la dernière version existante (brouillon en priorité, sinon la plus récente)
            ver = (doc.versions.order_by("-created_at").first()
                   or LegalVersion(document=doc, version="", status="draft"))

    if request.method == "POST":
        doc_form = LegalDocumentForm(request.POST, instance=doc)
        # Si le doc n’existe pas encore, on le crée d’abord pour lier la version
        if doc_form.is_valid():
            doc = doc_form.save()  # crée si nouveau
            # Prépare la version ciblée (si nouvelle, on l’instancie maintenant)
            if not ver or not ver.pk:
                ver = LegalVersion(document=doc)
            ver_form = LegalVersionForm(request.POST, instance=ver)
            if ver_form.is_valid():
                v = ver_form.save(commit=False)
                v.updated_by = request.user
                # Si on publie et qu’aucune date de publication n’existe, rends le markdown -> html et publie
                if v.status == "published" and not v.published_at:
                    v.render_markdown()
                    v.published_at = timezone.now()
                else:
                    # Toujours rendre le markdown pour avoir body_html à jour même en brouillon
                    v.render_markdown()
                v.save()
                return redirect("staff:legal_list")
        else:
            # si doc_form invalide, on doit quand même instancier ver_form pour réafficher le formulaire
            ver_form = LegalVersionForm(request.POST, instance=ver if ver and ver.pk else None)
    else:
        doc_form = LegalDocumentForm(instance=doc)
        ver_form = LegalVersionForm(instance=ver)

    return render(request, "staff/legal_edit.html", {
        "doc_form": doc_form,
        "ver_form": ver_form,
        "doc": doc,
        "ver": ver,
    })
