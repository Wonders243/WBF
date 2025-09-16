# accounts/urls.py
from django.urls import path
from . import views
from staff import views as staff_views   

app_name = 'benevoles'

urlpatterns = [
    path('profile_benevole/', views.profile_benevole, name='profile_benevole'),
    path("profile_benevole/edit/", views.profile_edit, name="profile_edit"),

    path("candidature/<int:pk>/", staff_views.application_detail, name="application_detail"),

    path('dashboard_benevole/', views.dashboard, name='dashboard'),

    path('documents/', views.UserDocuments_list, name='UserDocuments_list'),
    path('documents/upload/', views.UserDocuments_upload, name='UserDocuments_upload'),
    path('documents/<int:pk>/delete/', views.UserDocuments_delete, name='documents_delete'),

    path("heures/declarer/", views.hours_entry_create, name="hours_entry_create"),

    path('historique/', views.historique_benevole, name='historique_benevole'),

    # Vérification de changement d'email
    path('email-change/<str:token>/', views.email_change_verify, name='email_change_verify'),

    path("notifications/", views.notifications_list, name="notifications"),
   
    # Nouvelle page bénévole : invitations + missions disponibles
    path("missions/", views.missions_browse, name="missions_browse"),
]
