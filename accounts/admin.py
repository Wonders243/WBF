from django.contrib import admin
from .models import (
    Volunteer, Availability, Skill, VolunteerSkill,
    UserDocument,
    HoursEntry, HoursEntryProof,
    ActivityItem
)



@admin.register(UserDocument)
class UserDocumentAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "uploaded_at", "mime", "size")
    list_filter  = ("mime", "uploaded_at")
    search_fields = ("name", "user__username")

class HoursEntryProofInline(admin.TabularInline):
    model = HoursEntryProof
    extra = 0
    readonly_fields = ("uploaded_at", "size", "content_type")

@admin.register(HoursEntry)
class HoursEntryAdmin(admin.ModelAdmin):
    list_display = ("volunteer", "date", "hours", "mission", "event", "note")
    list_filter  = ("date", "mission", "event")
    search_fields = ("volunteer__user__username", "note")
    inlines = [HoursEntryProofInline]



@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ("volunteer", "day", "slot")
    list_filter  = ("day", "slot")



@admin.register(VolunteerSkill)
class VolunteerSkillAdmin(admin.ModelAdmin):
    list_display = ("volunteer", "skill", "level")
    list_filter  = ("level", "skill")

@admin.register(ActivityItem)
class ActivityItemAdmin(admin.ModelAdmin):
    list_display = ("volunteer", "title", "date")
    list_filter  = ("date",)
    search_fields = ("title", "volunteer__user__username")


class AvailabilityInline(admin.TabularInline):
    model = Availability
    extra = 0

class VolunteerSkillInline(admin.TabularInline):
    model = VolunteerSkill
    extra = 0

@admin.register(Volunteer)
class VolunteerAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "email", "user")
    search_fields = ("name", "email", "user__username")
    inlines = [AvailabilityInline, VolunteerSkillInline]

@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    search_fields = ("name",)



