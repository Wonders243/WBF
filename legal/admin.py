from django.contrib import admin
from .models import LegalDocument, LegalVersion, LegalAcceptance

@admin.register(LegalDocument)
class LegalDocumentAdmin(admin.ModelAdmin):
    list_display = ("title","key","locale","slug","created_at")
    list_filter = ("key","locale")
    search_fields = ("title","slug")

class LegalVersionInline(admin.TabularInline):
    model = LegalVersion
    extra = 0
    fields = ("version","status","effective_date","published_at","updated_at")
    readonly_fields = ("published_at","updated_at")

@admin.register(LegalVersion)
class LegalVersionAdmin(admin.ModelAdmin):
    list_display = ("document","version","status","effective_date","published_at","updated_by","updated_at")
    list_filter = ("status","document__key","document__locale")
    search_fields = ("document__title","version","change_log")
    readonly_fields = ("published_at","updated_at","created_at","updated_by")
    actions = ["action_publish","action_render"]

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Publier la version sélectionnée")
    def action_publish(self, request, qs):
        n = 0
        for v in qs:
            v.publish(user=request.user); n += 1
        self.message_user(request, f"{n} version(s) publiée(s).")

    @admin.action(description="Rendre le Markdown en HTML (sans publier)")
    def action_render(self, request, qs):
        for v in qs:
            v.render_markdown(); v.save()
        self.message_user(request, "Rendu HTML mis à jour.")

@admin.register(LegalAcceptance)
class LegalAcceptanceAdmin(admin.ModelAdmin):
    list_display = ("user","document","version","accepted_at","ip")
    list_filter = ("document__key","version__version")
    search_fields = ("user__username","user__email","version__version","ip")
