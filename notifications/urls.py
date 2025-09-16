from django.urls import path
from . import views

app_name = "notifications"
urlpatterns = [
    path("", views.list_notifications, name="list"),
    path("read-all/", views.mark_all_read, name="read_all"),
    path("open/<int:pk>/", views.open_notification, name="open"),
]
