# accounts/views_helpers.py
from django.db import models
from .models import HoursEntry, HoursEntryProof

def create_hours_proof(entry: HoursEntry, uploaded_file, user):
    """
    Crée un justificatif pour l'entrée 'entry' en détectant automatiquement :
      - le champ File/Image (ex: 'file', 'document', 'proof_file', ...)
      - le FK vers HoursEntry (ex: 'entry', 'hours_entry', 'hours', ...)
      - le champ 'uploaded_by' s'il existe (sinon ignoré)
    """
    Proof = HoursEntryProof

    # Champs concrets (pas les relations inverses)
    concrete = {f.name: f for f in Proof._meta.get_fields() if getattr(f, "concrete", False)}

    # 1) Trouver le FK vers HoursEntry
    fk_name = None
    for name, f in concrete.items():
        if getattr(f, "is_relation", False) and getattr(f, "many_to_one", False):
            if getattr(f.remote_field, "model", None) is HoursEntry:
                fk_name = name
                break

    # 2) Trouver le champ fichier
    file_name = None
    for name, f in concrete.items():
        internal = getattr(f, "get_internal_type", lambda: "")()
        if internal in ("FileField", "ImageField"):
            file_name = name
            break

    if not fk_name or not file_name:
        raise RuntimeError(
            f"Impossible de détecter le FK HoursEntry ({fk_name!r}) ou le champ fichier ({file_name!r}) "
            f"sur {Proof.__name__}. Champs disponibles: {list(concrete.keys())}"
        )

    kwargs = {
        fk_name: entry,
        file_name: uploaded_file,
    }

    # 3) Optionnel: 'uploaded_by'
    if "uploaded_by" in concrete:
        kwargs["uploaded_by"] = user

    return Proof.objects.create(**kwargs)
