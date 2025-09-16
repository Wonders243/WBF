from django.contrib import admin
from .models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "provider", "provider_tx_id", "amount", "currency", "status", "created_at")
    list_filter = ("provider", "status", "currency", "created_at")
    search_fields = ("provider_tx_id", "provider_ref", "email", "phone_e164", "name")
    readonly_fields = ("created_at", "updated_at", "raw_request", "raw_response", "raw_check")
