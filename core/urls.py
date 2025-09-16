from django.urls import path, include
from . import views

from django.views.generic import TemplateView

app_name = "core"

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("nous/", views.nous, name="nous"),

    # --- Projets ---
    path("project/", views.ProjectListView.as_view(), name="project"),
    path("project/<slug:slug>/", views.ProjectDetailView.as_view(), name="project_detail"),
    # Legacy (pk) -> redirection vers slug
    path("project_detail/<int:pk>/", views.project_detail_legacy, name="project_detail_legacy"),

    # --- Evénements ---
    path("events/", views.EventListView.as_view(), name="events_list"),
    path("events/<slug:slug>/", views.EventDetailView.as_view(), name="event_detail"),
    # Legacy (pk) -> redirection vers slug
    path("events/<int:pk>/", views.event_detail_legacy, name="event_detail_legacy"),

    # --- Dons ---
    path("don/", views.donation_create, name="don"),
    path("don/success/", views.donation_success, name="don_success"),
    path("don/return/", views.don_return, name="don_return"),

    # --- contact ---
    path("contact/", views.contact, name="contact"),
]


urlpatterns += [
    # Place the static route before the dynamic token route to avoid catching 'thanks' as token
    path("team/complete/thanks/", TemplateView.as_view(template_name="team/complete_thanks.html"), name="team_member_thanks"),
    path("team/complete/<str:token>/", views.team_member_complete, name="team_complete"),
    path("bientot/", views.coming_soon, name="coming_soon"),
    # Paiements (webhook Flutterwave)
    path("payments/flutterwave/webhook/", views.flutterwave_webhook, name="flw_webhook"),
]

from .views_services import service_education_orphelins, service_sante, service_soutien_psychologique

urlpatterns += [
    path("services/education/orphelins/", service_education_orphelins, name="service_education_orphelins"),
    path("services/sante/", service_sante, name="service_sante"),
    path("services/soutien-psychologique/", service_soutien_psychologique, name="service_psy"),
]
