from .models import LegalDocument, LegalAcceptance

def legal_outdated(request):
    if not request.user.is_authenticated:
        return {}
    outdated = []
    for key in ("privacy","terms"):
        try:
            doc = LegalDocument.objects.get(key=key, locale="fr")
        except LegalDocument.DoesNotExist:
            continue
        current = doc.current_version()
        if not current: 
            continue
        accepted = LegalAcceptance.objects.filter(user=request.user, document=doc).order_by("-accepted_at").first()
        if not accepted or accepted.version_id != current.id:
            outdated.append({"doc": doc, "ver": current})
    return {"legal_outdated_docs": outdated}
