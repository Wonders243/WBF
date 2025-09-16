from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from notifications.models import Notification


class Command(BaseCommand):
    help = "Purge old notifications (default: older than 90 days)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=90, help="Delete notifications older than N days (default 90)")

    def handle(self, *args, **options):
        days = options["days"]
        cutoff = timezone.now() - timedelta(days=days)
        qs = Notification.objects.filter(created_at__lt=cutoff)
        count = qs.count()
        qs.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} notifications older than {days} days."))

