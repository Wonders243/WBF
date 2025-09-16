# benevoles/services.py
from django.contrib.auth.models import Group
from django.apps import apps


def ensure_volunteer_account(user):
    group, _ = Group.objects.get_or_create(name="Bénévoles")
    user.groups.add(group)


    VolunteerModel = None
    for app_label in ("benevoles", "staff"):
        try:
            VolunteerModel = apps.get_model(app_label, "Volunteer")
            break
        except LookupError:
            continue
    if VolunteerModel:
        VolunteerModel.objects.get_or_create(user=user)