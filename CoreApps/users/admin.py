# CoreApps/users/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Business, StaffMember, Customer

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'username', 'first_name', 'last_name', 'is_staff')
    search_fields = ('email', 'username', 'first_name', 'last_name')

@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'user', 'service_delivery_type', 'business_type', 'is_active')
    list_filter = ('business_type', 'is_active', 'service_delivery_type')
    search_fields = ('display_name', 'user__email', 'slug')
    prepopulated_fields = {'slug': ('display_name',)}
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Información Principal', {
            'fields': ('user', 'display_name', 'slug', 'photo', 'bio')
        }),
        ('Configuración del Negocio', {
            'fields': ('business_type', 'location_name', 'address', 'is_active')
        }),
        ('Configuración de Servicios y Domicilio', {
            'fields': ('service_delivery_type', 'travel_buffer')
        }),
        # --- NUEVA SECCIÓN DE PERSONALIZACIÓN ---
        ('Personalización Visual', {
            'fields': ('primary_color', 'secondary_color'),
            'classes': ('collapse',), # Opcional: Oculta esta sección por defecto
        }),
    )

@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'is_active')
    list_filter = ('business', 'is_active')
    search_fields = ('name', 'business__display_name')

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'business', 'email', 'phone_number', 'address_line')
    search_fields = ('first_name', 'last_name', 'email', 'business__display_name', 'address_line')
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Información de Contacto', {
            'fields': ('user', 'business', 'first_name', 'last_name', 'email', 'phone_number')
        }),
        # --- NUEVA SECCIÓN DE DOMICILIO ---
        ('Información de Domicilio', {
            'fields': ('address_line', 'latitude', 'longitude'),
        }),
    )