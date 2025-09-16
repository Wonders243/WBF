from django.urls import path
from . import views
app_name = "legal"

urlpatterns = [
    path("confidentialite/", views.privacy, name="privacy"),
    path("conditions/",      views.terms,   name="terms"),
    path("cookies/",         views.cookies, name="cookies"),
    path("mentions-legales/",views.imprint, name="imprint"),

    path("legal/<str:key>/<str:locale>/history/", views.history, name="history"),
    path("legal/<str:key>/<str:locale>/api/current/", views.api_current, name="api_current"),
    path("legal/<str:key>/<str:locale>/accept/", views.accept, name="accept"),
    path("legal/<str:key>/<str:version>/<str:locale>/preview/", views.preview_version, name="preview"),
]
