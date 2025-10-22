from django.contrib import admin
from .models import Service, Product

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'price', 'duration', 'location_type', 'is_active')
    list_filter = ('is_active', 'business', 'location_type')
    search_fields = ('name', 'business__display_name')
    filter_horizontal = ('assignees',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'price', 'stock_quantity', 'is_active')
    list_filter = ('is_active', 'business')
    search_fields = ('name', 'business__display_name')