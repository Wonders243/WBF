from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth import get_user_model

from core.models import SiteStats
from accounts.models import Volunteer
from staff.models import Mission, MissionSignup
from core.models import TeamMember  # ton modèle staff est ici

# Optionnel: heures si présentes
try:
    from accounts.models import HoursEntry
    HAS_HOURS = True
except Exception:
    HAS_HOURS = False

def _recount(stats: SiteStats):
    U = get_user_model()
    stats.total_users = U.objects.count()
    stats.total_volunteers = Volunteer.objects.count()
    stats.total_staff = TeamMember.objects.count()
    stats.total_missions = Mission.objects.count()
    stats.total_signups = MissionSignup.objects.count()
    if HAS_HOURS:
        stats.total_hours_entries = HoursEntry.objects.count()
    stats.save()

@receiver(post_save, sender=Volunteer)
@receiver(post_delete, sender=Volunteer)
@receiver(post_save, sender=TeamMember)
@receiver(post_delete, sender=TeamMember)
@receiver(post_save, sender=Mission)
@receiver(post_delete, sender=Mission)
@receiver(post_save, sender=MissionSignup)
@receiver(post_delete, sender=MissionSignup)
def _on_core_change(sender, **kwargs):
    stats = SiteStats.get()
    _recount(stats)

if HAS_HOURS:
    @receiver(post_save, sender=HoursEntry)
    @receiver(post_delete, sender=HoursEntry)
    def _on_hours_change(sender, **kwargs):
        stats = SiteStats.get()
        _recount(stats)
