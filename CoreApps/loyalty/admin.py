from django.contrib import admin
from .models import LoyaltyCard, LoyaltyLog

class LoyaltyLogInline(admin.TabularInline):
    model = LoyaltyLog
    extra = 1
    readonly_fields = ('timestamp',)

@admin.register(LoyaltyCard)
class LoyaltyCardAdmin(admin.ModelAdmin):
    list_display = ('customer', 'points', 'tier_level')
    search_fields = ('customer__first_name', 'customer__last_name', 'customer__email')
    readonly_fields = ('created_at',)
    inlines = [LoyaltyLogInline]