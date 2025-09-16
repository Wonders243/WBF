from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from core.models import SiteStats

@staff_member_required
def super_stats_dashboard(request):
    stats = SiteStats.get()
    return render(request, "staff/super_stats_dashboard.html", {"stats": stats})
