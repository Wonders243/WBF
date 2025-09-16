# core/views_services.py
from django.shortcuts import render
from django.db.utils import OperationalError
from django.templatetags.static import static

try:
    from core.models import EducationStory, Partenaire, City
except Exception:  # graceful fallback if models missing
    EducationStory = None
    Partenaire = None
    City = None


def service_education_orphelins(request):
    story = None
    if EducationStory is not None:
        qs = (
            EducationStory.objects.filter(is_published=True)
            .select_related("city")
            .prefetch_related("images")
        )
        # Tente de filtrer par catégorie Éducation, sinon retombe sans filtre (migration non appliquée)
        try:
            try:
                qs = qs.filter(category=EducationStory.Category.EDUCATION)
            except Exception:
                qs = qs.filter(category='education') if hasattr(EducationStory, 'category') else qs
            story = qs.first()
        except OperationalError:
            story = (
                EducationStory.objects.filter(is_published=True)
                .select_related("city")
                .prefetch_related("images")
                .first()
            )

    # Placeholder statique pour le hero
    placeholder = static("img/placeholder-16x9.jpg")

    # HERO URL
    hero_url = placeholder
    consent_ok = bool(story and getattr(story, "consent_file", None))
    consent_ok = bool(story and getattr(story, "consent_file", None))
    consent_ok = bool(story and getattr(story, "consent_file", None))
    if consent_ok and getattr(story, "cover", None):
        try:
            if story.cover:
                hero_url = story.cover.url
        except Exception:
            pass
    if consent_ok and hero_url == placeholder:
        # 1ère image de la galerie
        try:
            first_img = next(iter(story.images.all()), None)
            if first_img and first_img.image:
                hero_url = first_img.image.url
        except Exception:
            pass

    # Galerie (liste d'URLs/légendes)
    gallery = []
    if consent_ok:
        for img in story.images.all():
            try:
                if img.image:
                    gallery.append({"url": img.image.url, "caption": img.caption})
            except Exception:
                continue

    # KPIs (calculs simples + fallback)
    kpi = {
        "children_supported": 0,
        "retention_rate": "—",
        "cities": 0,
        "partners": 0,
        "city_names": "Kinshasa, Kisangani, Goma, Lubumbashi",
    }
    try:
        if EducationStory is not None:
            qs = EducationStory.objects.filter(is_published=True)
            try:
                qs = qs.filter(category=EducationStory.Category.EDUCATION)
            except Exception:
                qs = qs.filter(category='education') if hasattr(EducationStory, 'category') else qs
            qs = qs.select_related("city")
            kpi["children_supported"] = qs.count()
            city_ids = [s.city_id for s in qs if getattr(s, "city_id", None)]
            if city_ids:
                unique_ids = list(dict.fromkeys(city_ids))
                kpi["cities"] = len(unique_ids)
                try:
                    names = list(City.objects.filter(id__in=unique_ids).values_list("name", flat=True)) if City else []
                    names = [n for n in names if n]
                    if names:
                        caption = ", ".join(names[:4]) + ("…" if len(names) > 4 else "")
                        kpi["city_names"] = caption
                except Exception:
                    pass
        if Partenaire is not None:
            kpi["partners"] = Partenaire.objects.count()
    except Exception:
        pass

    return render(
        request,
        "services/education_orphelins.html",
        {
            "story": story,
            "hero_url": hero_url,
            "gallery": gallery,
            "kpi": kpi,
        },
    )


def service_sante(request):
    story = None
    if EducationStory is not None:
        qs = (
            EducationStory.objects.filter(is_published=True)
            .select_related("city")
            .prefetch_related("images")
        )
        try:
            try:
                qs = qs.filter(category=getattr(EducationStory.Category, 'SANTE', 'sante'))
            except Exception:
                qs = qs.filter(category='sante') if hasattr(EducationStory, 'category') else qs
            story = qs.first()
        except OperationalError:
            story = (
                EducationStory.objects.filter(is_published=True)
                .select_related("city")
                .prefetch_related("images")
                .first()
            )

    placeholder = static("img/placeholder-16x9.jpg")
    hero_url = placeholder
    consent_ok = bool(story and getattr(story, "consent_file", None))
    if consent_ok and getattr(story, "cover", None):
        try:
            if story.cover:
                hero_url = story.cover.url
        except Exception:
            pass
    if consent_ok and hero_url == placeholder:
        try:
            first_img = next(iter(story.images.all()), None)
            if first_img and first_img.image:
                hero_url = first_img.image.url
        except Exception:
            pass

    gallery = []
    if consent_ok:
        for img in story.images.all():
            try:
                if img.image:
                    gallery.append({"url": img.image.url, "caption": img.caption})
            except Exception:
                continue

    kpi = {
        "children_supported": 0,
        "retention_rate": "-",
        "cities": 0,
        "partners": 0,
        "city_names": "",
    }
    try:
        if EducationStory is not None:
            qs = EducationStory.objects.filter(is_published=True)
            try:
                qs = qs.filter(category=getattr(EducationStory.Category, 'SANTE', 'sante'))
            except Exception:
                qs = qs.filter(category='sante') if hasattr(EducationStory, 'category') else qs
            qs = qs.select_related("city")
            kpi["children_supported"] = qs.count()
            city_ids = [s.city_id for s in qs if getattr(s, "city_id", None)]
            if city_ids:
                unique_ids = list(dict.fromkeys(city_ids))
                kpi["cities"] = len(unique_ids)
                try:
                    names = list(City.objects.filter(id__in=unique_ids).values_list("name", flat=True)) if City else []
                    names = [n for n in names if n]
                    if names:
                        caption = ", ".join(names[:4]) + ("…" if len(names) > 4 else "")
                        kpi["city_names"] = caption
                except Exception:
                    pass
        if Partenaire is not None:
            kpi["partners"] = Partenaire.objects.count()
    except Exception:
        pass

    return render(
        request,
        "services/sante.html",
        {
            "story": story,
            "hero_url": hero_url,
            "gallery": gallery,
            "kpi": kpi,
        },
    )


def service_soutien_psychologique(request):
    story = None
    if EducationStory is not None:
        qs = (
            EducationStory.objects.filter(is_published=True)
            .select_related("city")
            .prefetch_related("images")
        )
        try:
            try:
                qs = qs.filter(category=getattr(EducationStory.Category, 'PSY', 'psy'))
            except Exception:
                qs = qs.filter(category='psy') if hasattr(EducationStory, 'category') else qs
            story = qs.first()
        except OperationalError:
            story = (
                EducationStory.objects.filter(is_published=True)
                .select_related("city")
                .prefetch_related("images")
                .first()
            )

    placeholder = static("img/placeholder-16x9.jpg")
    hero_url = placeholder
    consent_ok = bool(story and getattr(story, "consent_file", None))
    if consent_ok and getattr(story, "cover", None):
        try:
            if story.cover:
                hero_url = story.cover.url
        except Exception:
            pass
    if consent_ok and hero_url == placeholder:
        try:
            first_img = next(iter(story.images.all()), None)
            if first_img and first_img.image:
                hero_url = first_img.image.url
        except Exception:
            pass

    gallery = []
    if consent_ok:
        for img in story.images.all():
            try:
                if img.image:
                    gallery.append({"url": img.image.url, "caption": img.caption})
            except Exception:
                continue

    kpi = {
        "children_supported": 0,
        "retention_rate": "-",
        "cities": 0,
        "partners": 0,
        "city_names": "",
    }
    try:
        if EducationStory is not None:
            qs = EducationStory.objects.filter(is_published=True)
            try:
                qs = qs.filter(category=getattr(EducationStory.Category, 'PSY', 'psy'))
            except Exception:
                qs = qs.filter(category='psy') if hasattr(EducationStory, 'category') else qs
            qs = qs.select_related("city")
            kpi["children_supported"] = qs.count()
            city_ids = [s.city_id for s in qs if getattr(s, "city_id", None)]
            if city_ids:
                unique_ids = list(dict.fromkeys(city_ids))
                kpi["cities"] = len(unique_ids)
                try:
                    names = list(City.objects.filter(id__in=unique_ids).values_list("name", flat=True)) if City else []
                    names = [n for n in names if n]
                    if names:
                        caption = ", ".join(names[:4]) + ("…" if len(names) > 4 else "")
                        kpi["city_names"] = caption
                except Exception:
                    pass
        if Partenaire is not None:
            kpi["partners"] = Partenaire.objects.count()
    except Exception:
        pass

    return render(
        request,
        "services/soutien_psychologique.html",
        {
            "story": story,
            "hero_url": hero_url,
            "gallery": gallery,
            "kpi": kpi,
        },
    )
