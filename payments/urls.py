from django.conf import settings
from django.urls import path
from . import views

app_name = "payments"

if getattr(settings, "PAYMENT_MAINTENANCE", False):
    urlpatterns = [
        # On détourne l’utilisateur vers la page maintenance
        path("rdc/start/", views.payment_maintenance, name="rdc_start"),
        path("return/",     views.payment_maintenance, name="return"),
        path("test/",       views.payment_maintenance, name="test"),

        # ⚠️ On laisse le webhook en vie !
        path("notify/", views.cinetpay_notify, name="notify"),
    ]
else:
    urlpatterns = [
        path("rdc/start/", views.donate_rdc_start, name="rdc_start"),
        path("return/",     views.cinetpay_return,  name="return"),
        path("notify/",     views.cinetpay_notify,  name="notify"),
        path("test/",       views.donate_test,      name="test"),
    ]
