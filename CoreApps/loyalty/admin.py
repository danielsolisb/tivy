from django.contrib import admin
from .models import LoyaltyCard, LoyaltyLog

class LoyaltyLogInline(admin.TabularInline):
    """
    Permite ver y añadir registros de lealtad directamente desde
    la vista de la Tarjeta de Lealtad.
    """
    model = LoyaltyLog
    extra = 1 # Muestra un campo extra para añadir un nuevo log
    readonly_fields = ('timestamp',)

@admin.register(LoyaltyCard)
class LoyaltyCardAdmin(admin.ModelAdmin):
    list_display = ('customer', 'points', 'tier_level')
    search_fields = ('customer__first_name', 'customer__last_name', 'customer__email')
    readonly_fields = ('created_at',)
    # Añade la vista de logs dentro de la tarjeta
    inlines = [LoyaltyLogInline]