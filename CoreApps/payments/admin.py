from django.contrib import admin
from .models import Transaction

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'business', 'amount', 'status', 'provider', 'created_at')
    list_filter = ('status', 'provider', 'business')
    search_fields = ('customer__email', 'business__display_name', 'provider_tx_id')
    readonly_fields = ('created_at', 'updated_at')