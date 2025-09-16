from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.forms import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from datetime import datetime

from core.models import News, Testimonial, EducationStory, EducationStoryImage
from .forms import NewsForm, TestimonialForm, EducationStoryForm


# ========= Contenu: Actualités =========
@staff_member_required
def news_list(request):
    q = (request.GET.get("q") or "").strip()
    frm = (request.GET.get("from") or "").strip()
    to = (request.GET.get("to") or "").strip()
    qs = News.objects.all()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(content__icontains=q))
    def _parse_date(s):
        try:
            return datetime.fromisoformat(s).date()
        except Exception:
            return None
    d1 = _parse_date(frm)
    d2 = _parse_date(to)
    if d1:
        qs = qs.filter(date__gte=d1)
    if d2:
        qs = qs.filter(date__lte=d2)
    page_obj = Paginator(qs.order_by("-date", "-id"), 12).get_page(request.GET.get("page"))
    return render(request, "staff/news_list.html", {"page_obj": page_obj})


@staff_member_required
def news_create(request):
    if request.method == "POST":
        form = NewsForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Actualité créée ✅")
            return redirect("staff:news_list")
    else:
        form = NewsForm()
    return render(request, "staff/news_form.html", {"form": form, "obj": None})


@staff_member_required
def news_update(request, pk):
    obj = get_object_or_404(News, pk=pk)
    if request.method == "POST":
        form = NewsForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Actualité mise à jour ✅")
            return redirect("staff:news_list")
    else:
        form = NewsForm(instance=obj)
    return render(request, "staff/news_form.html", {"form": form, "obj": obj})


@staff_member_required
def news_delete(request, pk):
    obj = get_object_or_404(News, pk=pk)
    if request.method == "POST":
        title = obj.title
        obj.delete()
        messages.success(request, f"Actualité supprimée: {title}")
        return redirect("staff:news_list")
    return render(request, "staff/news_confirm_delete.html", {"obj": obj})


# ========= Contenu: Témoignages =========
@staff_member_required
def testimonials_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = Testimonial.objects.all()
    if q:
        qs = qs.filter(Q(author__icontains=q) | Q(content__icontains=q))
    page_obj = Paginator(qs.order_by("-id"), 12).get_page(request.GET.get("page"))
    return render(request, "staff/testimonials_list.html", {"page_obj": page_obj})


@staff_member_required
def testimonial_create(request):
    if request.method == "POST":
        form = TestimonialForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Témoignage créé ✅")
            return redirect("staff:testimonials_list")
    else:
        form = TestimonialForm()
    return render(request, "staff/testimonial_form.html", {"form": form, "obj": None})


@staff_member_required
def testimonial_update(request, pk):
    obj = get_object_or_404(Testimonial, pk=pk)
    if request.method == "POST":
        form = TestimonialForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Témoignage mis à jour ✅")
            return redirect("staff:testimonials_list")
    else:
        form = TestimonialForm(instance=obj)
    return render(request, "staff/testimonial_form.html", {"form": form, "obj": obj})


@staff_member_required
def testimonial_delete(request, pk):
    obj = get_object_or_404(Testimonial, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Témoignage supprimé")
        return redirect("staff:testimonials_list")
    return render(request, "staff/testimonial_confirm_delete.html", {"obj": obj})


# ========= Contenu: Histoires Education =========
@staff_member_required
def stories_list(request):
    q = (request.GET.get("q") or "").strip()
    cat = (request.GET.get("category") or "").strip()
    qs = EducationStory.objects.all()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(beneficiary_name__icontains=q))
    if cat:
        qs = qs.filter(category=cat)
    page_obj = Paginator(qs.order_by("-created_at", "-id"), 12).get_page(request.GET.get("page"))
    return render(request, "staff/stories_list.html", {"page_obj": page_obj})


@staff_member_required
def story_create(request):
    if request.method == "POST":
        form = EducationStoryForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Histoire créée ✅")
            return redirect("staff:stories_list")
    else:
        form = EducationStoryForm()
    return render(request, "staff/story_form.html", {"form": form, "obj": None})


@staff_member_required
def story_update(request, pk):
    obj = get_object_or_404(EducationStory, pk=pk)
    if request.method == "POST":
        form = EducationStoryForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Histoire mise à jour ✅")
            return redirect("staff:stories_list")
    else:
        form = EducationStoryForm(instance=obj)
    return render(request, "staff/story_form.html", {"form": form, "obj": obj})


@staff_member_required
def story_images(request, pk):
    story = get_object_or_404(EducationStory, pk=pk)
    ImageFormSet = inlineformset_factory(
        EducationStory,
        EducationStoryImage,
        fields=["image", "caption", "sort_order"],
        extra=3,
        can_delete=True,
    )
    if request.method == "POST":
        formset = ImageFormSet(request.POST, request.FILES, instance=story)
        if formset.is_valid():
            formset.save()
            messages.success(request, "Images mises à jour ✅")
            return redirect("staff:stories_list")
    else:
        formset = ImageFormSet(instance=story)
    return render(request, "staff/story_images_form.html", {"story": story, "formset": formset})


@staff_member_required
def story_delete(request, pk):
    obj = get_object_or_404(EducationStory, pk=pk)
    if request.method == "POST":
        title = obj.title
        obj.delete()
        messages.success(request, f"Histoire supprimée: {title}")
        return redirect("staff:stories_list")
    return render(request, "staff/story_confirm_delete.html", {"obj": obj})


@staff_member_required
@require_POST
def story_toggle_published(request, pk):
    obj = get_object_or_404(EducationStory, pk=pk)
    obj.is_published = not obj.is_published
    obj.save(update_fields=["is_published"])
    messages.info(request, f"Publication: {'activée' if obj.is_published else 'désactivée'}")
    return redirect("staff:stories_list")
