from django.contrib import admin
from .models import (
    TeamMember, Partenaire, Project, Event,
    Testimonial, News, Donation,
    ContactMessage, City
)
from staff.models import VolunteerApplication

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "province", "country_code")
    search_fields = ("name", "province")
    list_filter = ("province",)
    
@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "slug")
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "date", "slug")
    list_filter  = ("date",)
    search_fields = ("titVolunteerApplicationAdmle", "description")
    prepopulated_fields = {"slug": ("title",)}

@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "seniority", "is_active", "user")
    list_filter = ("is_active", "seniority", "department")
    search_fields = ("name", "role", "email", "user__username", "user__email")
    raw_id_fields = ("user",)
    ordering = ("sort_order", "name")

@admin.register(Partenaire)
class PartenaireAdmin(admin.ModelAdmin):
    list_display = ("name", "website")
    search_fields = ("name",)

@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ("author",)
    search_fields = ("author", "content")

@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ("title", "date")
    list_filter  = ("date",)
    search_fields = ("title", "content")

@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ("donor_name", "amount", "date")
    list_filter  = ("date",)
    search_fields = ("donor_name",)

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "date_sent")
    list_filter  = ("date_sent",)
    search_fields = ("name", "email", "subject", "message")

# core/admin.py
from django.contrib import admin
from .models import EducationStory, EducationStoryImage

class EducationStoryImageInline(admin.TabularInline):
    model = EducationStoryImage
    extra = 1

@admin.register(EducationStory)
class EducationStoryAdmin(admin.ModelAdmin):
    list_display = ("title", "city", "is_published", "created_at")
    list_filter = ("is_published", "city")
    search_fields = ("title", "beneficiary_name")
    inlines = [EducationStoryImageInline]
