from django.contrib import admin
from .models import Mission, MissionSignup, VolunteerApplication 
from .security.models import AuthorizationKey, AuthorizationKeyUse
from django.utils import timezone


class MissionSignupInline(admin.TabularInline):
    model = MissionSignup
    extra = 0
    autocomplete_fields = ("volunteer",)
    readonly_fields = ("responded_at", "created_at")

@admin.register(Mission)
class MissionAdmin(admin.ModelAdmin):
    list_display = ("title", "event", "start_date", "status", "capacity")
    list_filter  = ("status", "event")
    search_fields = ("title", "description", "event__title")
    date_hierarchy = "start_date"
    inlines = [MissionSignupInline]

@admin.register(MissionSignup)
class MissionSignupAdmin(admin.ModelAdmin):
    list_display = ("mission", "volunteer", "status", "responded_at", "created_at")
    list_filter  = ("status", "mission__event")
    search_fields = ("mission__title", "volunteer__name", "volunteer__user__username")

@admin.register(AuthorizationKey)
class AuthorizationKeyAdmin(admin.ModelAdmin):
    list_display = ("label", "token_prefix", "level", "is_active", "uses_count", "max_uses", "expires_at", "created_by", "created_at")
    list_filter = ("is_active", "level")
    search_fields = ("label", "token_prefix", "created_by__username")
    readonly_fields = ("uses_count", "created_at")
    actions = ["activer", "desactiver"]

    @admin.action(description="Activer les clés sélectionnées")
    def activer(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Désactiver les clés sélectionnées")
    def desactiver(self, request, queryset):
        queryset.update(is_active=False)


@admin.register(AuthorizationKeyUse)
class AuthorizationKeyUseAdmin(admin.ModelAdmin):
    list_display = ("used_at", "action", "success", "used_by", "key", "ip")
    list_filter = ("success", "action")
    search_fields = ("used_by__username", "action", "ip", "user_agent")
    date_hierarchy = "used_at"


@admin.register(VolunteerApplication)
class VolunteerApplicationAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "submitted_at", "reviewed_at")
    list_filter = ("status",)
    search_fields = ("user__username", "user__email", "motivation")
    date_hierarchy = "submitted_at"
    actions = ["approve_applications", "reject_applications"]

    @admin.action(description="Approuver les candidatures sélectionnées")
    def approve_applications(self, request, queryset):
        updated = queryset.update(status='approved', reviewed_at=timezone.now())
        self.message_user(request, f"{updated} candidatures approuvées.")

    @admin.action(description="Rejeter les candidatures sélectionnées")
    def reject_applications(self, request, queryset):
        updated = queryset.update(status='rejected', reviewed_at=timezone.now())
        self.message_user(request, f"{updated} candidatures rejetées.")

admin.site.site_header = "Administration WBF"