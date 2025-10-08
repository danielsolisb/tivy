from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Client, Customer

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'username', 'first_name', 'last_name', 'is_staff')
    search_fields = ('email', 'username', 'first_name', 'last_name')

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    # Añadimos los nuevos campos a la vista de lista
    list_display = ('display_name', 'user', 'service_delivery_type', 'business_type', 'is_active')
    list_filter = ('business_type', 'is_active', 'service_delivery_type')
    search_fields = ('display_name', 'user__email', 'slug')
    prepopulated_fields = {'slug': ('display_name',)}
    readonly_fields = ('created_at',)

    # Organizamos el formulario de edición en secciones para mayor claridad
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
    )

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'client', 'email', 'phone_number')
    search_fields = ('first_name', 'last_name', 'email', 'client__display_name')
    readonly_fields = ('created_at',)