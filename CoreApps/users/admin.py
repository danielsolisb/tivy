# CoreApps/users/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
# Añadimos los nuevos modelos a la importación
from .models import User, Business, StaffMember, Customer, Plan, Subscription

# UserAdmin sin cambios
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'username', 'first_name', 'last_name', 'is_staff')
    search_fields = ('email', 'username', 'first_name', 'last_name')

# Inline para mostrar la Suscripción dentro del Business
class SubscriptionInline(admin.StackedInline):
    model = Subscription
    extra = 0 # No mostrar formularios extra para añadir
    readonly_fields = ('created_at', 'updated_at') # Campos de solo lectura

@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'user', 'get_plan_name', 'get_subscription_status', 'is_active') # Métodos para mostrar info de suscripción
    list_filter = ('business_type', 'is_active', 'service_delivery_type', 'subscription__plan', 'subscription__status') # Filtrar por plan y estado
    search_fields = ('display_name', 'user__email', 'slug')
    prepopulated_fields = {'slug': ('display_name',)}
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Información Principal', {'fields': ('user', 'display_name', 'slug', 'photo', 'bio')}),
        ('Configuración del Negocio', {'fields': ('business_type', 'location_name', 'address', 'is_active')}),
        ('Configuración de Servicios y Domicilio', {'fields': ('service_delivery_type', 'travel_buffer')}),
        ('Personalización Visual', {'fields': ('primary_color', 'secondary_color'), 'classes': ('collapse',)}),
    )
    inlines = [SubscriptionInline] # Añadimos el inline de suscripción

    # Métodos helper para mostrar datos relacionados en list_display
    @admin.display(description='Plan Actual')
    def get_plan_name(self, obj):
        return obj.subscription.plan.name if hasattr(obj, 'subscription') and obj.subscription and obj.subscription.plan else 'N/A'

    @admin.display(description='Estado Suscripción')
    def get_subscription_status(self, obj):
        return obj.subscription.get_status_display() if hasattr(obj, 'subscription') and obj.subscription else 'N/A'

# StaffMemberAdmin sin cambios
@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'is_active')
    list_filter = ('business', 'is_active')
    search_fields = ('name', 'business__display_name')

# CustomerAdmin sin cambios estructurales, solo añadimos address_line a list_display si no estaba
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'business', 'email', 'phone_number', 'address_line')
    search_fields = ('first_name', 'last_name', 'email', 'business__display_name', 'address_line')
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Información de Contacto', {'fields': ('user', 'business', 'first_name', 'last_name', 'email', 'phone_number')}),
        ('Información de Domicilio', {'fields': ('address_line', 'latitude', 'longitude')}),
    )

# --- NUEVOS REGISTROS ADMIN ---
@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price_monthly', 'max_staff', 'allow_payments', 'is_active')
    list_filter = ('is_active',)

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('business', 'plan', 'status', 'trial_end_date', 'current_period_end')
    list_filter = ('plan', 'status')
    search_fields = ('business__display_name',)
    readonly_fields = ('created_at', 'updated_at')