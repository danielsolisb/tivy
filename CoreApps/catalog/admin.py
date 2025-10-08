from django.contrib import admin
from .models import Service, Product

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    # Añadimos location_type a la lista y a los filtros
    list_display = ('name', 'client', 'price', 'duration', 'location_type', 'is_active')
    list_filter = ('is_active', 'client', 'location_type')
    search_fields = ('name', 'client__display_name')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'client', 'price', 'stock_quantity', 'is_active')
    list_filter = ('is_active', 'client')
    search_fields = ('name', 'client__display_name')