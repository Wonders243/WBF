from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import TeamMember
from accounts.models import Volunteer

@receiver(post_save, sender=TeamMember)
def ensure_volunteer_for_staff(sender, instance: TeamMember, created, **kwargs):
    if instance.user_id and not hasattr(instance.user, "volunteer"):
        vol = Volunteer.objects.create(
            user=instance.user,
            name=(instance.name or instance.user.get_full_name() or instance.user.get_username())
        )
        # pas de champ city ici: on laisse l’humain le compléter
