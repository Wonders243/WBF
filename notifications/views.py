from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Notification
from django.http import HttpResponse

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages


@login_required
def list_notifications(request):
    qs = Notification.objects.filter(recipient=request.user).select_related("actor")
    return render(request, "notifications/list.html", {"notifications": qs})


@login_required
def mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    if request.method == "POST":
        return HttpResponse(status=204)
    from django.shortcuts import redirect
    return redirect("notifications:list")


@login_required
def open_notification(request, pk):
    n = get_object_or_404(Notification, pk=pk, recipient=request.user)

    # marque comme lu
    if not n.is_read:
        n.is_read = True
        n.save(update_fields=["is_read"])

    # Choix du lien: staff -> privilégie l'URL stockée par-notif; bénévole -> cible directe d'abord
    url = ""
    if request.user.is_staff:
        url = n.url or ""
        if not url and n.target:
            try:
                url = n.target.get_absolute_url()
            except Exception:
                url = ""
    else:
        if n.target:
            try:
                url = n.target.get_absolute_url()
            except Exception:
                url = ""
        if not url:
            url = n.url or ""

    if url:
        return redirect(url)

    messages.warning(request, "Cet élément n'existe plus ou n'est pas accessible.")
    return redirect("notifications:list")

