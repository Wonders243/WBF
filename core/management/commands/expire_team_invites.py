from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import TeamMemberInvite


class Command(BaseCommand):
    help = "Expire outdated team member invites (expires_at < now, unused)."

    def handle(self, *args, **options):
        now = timezone.now()
        qs = TeamMemberInvite.objects.filter(used_at__isnull=True, expires_at__lt=now)
        count = qs.count()
        # Nothing to update if already expired logically; just report
        self.stdout.write(self.style.SUCCESS(f"Outdated invites found: {count}"))
        # Optionally force expires_at to now (idempotent)
        qs.update(expires_at=now)
        self.stdout.write(self.style.SUCCESS("Invitations flagged as expired."))

