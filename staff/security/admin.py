# security/admin.py
from django.contrib import admin
from .models import AuthorizationKey, AuthorizationKeyUse

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
