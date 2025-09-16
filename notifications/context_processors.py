from .models import Notification

def notifications_badge(request):
    if request.user.is_authenticated:
        return {
            "unread_notifications": Notification.objects.filter(
                recipient=request.user, is_read=False
            ).count()
        }
    return {}
