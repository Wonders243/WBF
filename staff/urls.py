# staff/urls.py
from django.urls import path
from . import views
from .security import views as security_views
from . import views_legal
from . import views_content


app_name = "staff"

urlpatterns = [

    # Dashboard
    path("", views.staff_dashboard, name="dashboard"),
    path("profile/", views.profil_staff, name="profil_staff"),
    path("users/<int:pk>/json/", views.staff_user_json, name="user_json"),
    

    # Missions
    path("missions/", views.missions_list, name="mission_list"),
    path("missions/new/", views.mission_create, name="mission_create"),
    path("missions/<int:pk>/", views.mission_detail, name="mission_detail"),
    path("missions/<int:pk>/edit/", views.mission_update, name="mission_update"),

    # staff/urls.py — remplace le bloc Inscriptions par :
    path("missions/signup/<int:signup_id>/accept/",  views.mission_accept,  name="mission_accept"),
    path("missions/signup/<int:signup_id>/decline/", views.mission_decline, name="mission_decline"),  # <-- à ajouter
    path("signups/<int:signup_id>/cancel/",          views.mission_cancel,  name="mission_cancel"),
    path("missions/<int:mission_id>/apply/",         views.mission_apply,   name="mission_apply"),
    path(
        "missions/invites/<int:signup_id>/cancel/",
        views.mission_cancel_invite,
        name="mission_cancel_invite",
    ),

     # Team
    path("team/", views.staff_team_list, name="team_list"),
    path("team/new/", views.staff_team_create, name="team_create"),
    
    path("team/<slug:slug>/edit/", views.staff_team_update, name="team_update"),
    path("team/<slug:slug>/invite/", views.staff_team_send_invite, name="staff_team_send_invite"),

    path("team/invite/", views.team_invite_picker, name="team_invite_picker"),
    path("team/<slug:slug>/", views.staff_team_detail, name="team_detail"),

    # ⚠️ harmonise ce nom avec tes templates
    path(
        "volunteers/<int:volunteer_id>/invite-to-team/",
        views.staff_volunteer_send_team_invite,
        name="volunteer_team_invite",
    ),
    
    path("team/invites/<int:invite_id>/revoke/", views.team_invite_revoke, name="team_invite_revoke"),
    path("team/invites/<int:invite_id>/resend/", views.team_invite_resend, name="team_invite_resend"),
    path("team/<slug:slug>/toggle-active/", views.team_member_toggle_active, name="team_member_toggle_active"),
    path("team/<slug:slug>/approve-access/", views.team_member_approve_access, name="team_member_approve_access"),
    

    # Partners
    path("partners/", views.staff_partner_list, name="partner_list"),
    path("partners/new/", views.staff_partner_create, name="partner_create"),
    path("partners/<slug:slug>/", views.staff_partner_detail, name="partner_detail"),
    path("partners/<slug:slug>/edit/", views.staff_partner_update, name="partner_update"),

    path("signups/<int:signup_id>/accept/", views.staff_signup_accept, name="staff_signup_accept"),
    path("signups/<int:signup_id>/decline/", views.staff_signup_decline, name="staff_signup_decline"),
    path("missions/<int:mission_id>/invite/", views.mission_invite, name="mission_invite"),

    # Missions en attente      
    path("missions/pending/<int:mission_id>/", views.mission_detail_alias,name="mission_detail_pending"),
    # Inscriptions (listing staff)
    path("signups/", views.signups_list, name="signups_list"),

    # Bénévoles
    path("volunteers/", views.volunteers_list, name="volunteers_list"),
    path("volunteers/<int:pk>/", views.volunteer_detail, name="volunteer_detail"),
    
    path("devenir/", views.application_start, name="application_start"),
    path("candidature/<int:pk>/", views.application_detail, name="application_detail"),


    path("applications/", views.staff_applications_list, name="applications_list"),
    path("applications/<int:pk>/", views.staff_application_review, name="application_review"),

    # Documents utilisateurs
    path("documents/", views.documents_review, name="documents_review"),

    # Heures déclarées
    path("hours/", views.hours_list, name="hours_list"),

    # Événements (staff)
    path("events/", views.events_list, name="events_list"),
    path("events/new/", views.event_create, name="event_create"),
    path("events/<int:pk>/", views.event_detail, name="event_detail"),
    path("events/<int:pk>/edit/", views.event_update, name="event_update"),


    # Projets (staff)
    path("projects/", views.projects_list, name="projects_list"),
    path("projects/new/", views.project_create, name="project_create"),
    path("projects/<int:pk>/", views.project_detail, name="project_detail"),
    path("projects/<int:pk>/edit/", views.project_update, name="project_update"),


    # Sécurité
    path("security/keys/", security_views.key_list, name="key_list"),
    path("security/keys/new/", security_views.create_auth_key, name="create_key"),
    path("keys/<uuid:key_id>/revoke/", security_views.revoke_key, name="revoke_key"),  # ✅ UUID
    #path("keys/<uuid:key_id>/send/", security_views.send_key, name="send_key"),        # (si tu l’as)

    path("security/keys/<uuid:key_id>/created/", security_views.key_created, name="key_created"),
    path("keys/<uuid:key_id>/rotate/", security_views.rotate_key, name="rotate_key"),

    path("legal/", views_legal.legal_list, name="legal_list"),
    path("legal/new/", views_legal.legal_edit, name="legal_new"),
    path("legal/<int:pk>/edit/", views_legal.legal_edit, name="legal_edit"),
    
]

from .views_stats import super_stats_dashboard
urlpatterns += [
    path("stats/", super_stats_dashboard, name="super_stats"),
]

# Contenu (Actualités, Témoignages, Histoires)
urlpatterns += [
    # News
    path("news/", views_content.news_list, name="news_list"),
    path("news/new/", views_content.news_create, name="news_create"),
    path("news/<int:pk>/edit/", views_content.news_update, name="news_update"),
    path("news/<int:pk>/delete/", views_content.news_delete, name="news_delete"),

    # Testimonials
    path("testimonials/", views_content.testimonials_list, name="testimonials_list"),
    path("testimonials/new/", views_content.testimonial_create, name="testimonial_create"),
    path("testimonials/<int:pk>/edit/", views_content.testimonial_update, name="testimonial_update"),
    path("testimonials/<int:pk>/delete/", views_content.testimonial_delete, name="testimonial_delete"),

    # Education stories
    path("stories/", views_content.stories_list, name="stories_list"),
    path("stories/new/", views_content.story_create, name="story_create"),
    path("stories/<int:pk>/edit/", views_content.story_update, name="story_update"),
    path("stories/<int:pk>/images/", views_content.story_images, name="story_images"),
    path("stories/<int:pk>/delete/", views_content.story_delete, name="story_delete"),
    path("stories/<int:pk>/toggle-published/", views_content.story_toggle_published, name="story_toggle_published"),
]
