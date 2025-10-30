# CoreApps/users/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Business, StaffMember, Customer, Plan, Subscription, ServiceZone
from django.utils.html import format_html # Necesario para enlaces (opcional)
from django.urls import reverse # Necesario para enlaces (opcional)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        'email',
        'username',
        'first_name',
        'last_name',
        'get_business_link', # Muestra el negocio (dueño o staff)
        'is_customer',
        'is_staff' # Permisos de admin
    )
    search_fields = ('email', 'username', 'first_name', 'last_name')
    # --- LÍNEA CORREGIDA ---
    # Eliminamos los filtros __isnull que no son soportados directamente
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')

    fieldsets = UserAdmin.fieldsets + (
            ('Campos Personalizados', {'fields': ('profile_image',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
            (None, {'fields': ('profile_image',)}),
    )

    @admin.display(description='Negocio Asociado')
    def get_business_link(self, obj):
        business = None
        role = None
        if hasattr(obj, 'business_profile') and obj.business_profile is not None:
            business = obj.business_profile
            role = "Dueño"
        elif hasattr(obj, 'staff_profile') and obj.staff_profile is not None:
            business = obj.staff_profile.business
            role = "Staff"
            
        if business:
            link = reverse("admin:users_business_change", args=[business.id])
            return format_html('<a href="{}">{} ({})</a>', link, business.display_name, role)
        return "N/A"

    @admin.display(boolean=True, description='Cliente?')
    def is_customer(self, obj):
        return obj.customer_profiles.exists()

        
class SubscriptionInline(admin.StackedInline):
    model = Subscription
    extra = 0
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    # Añadimos city y country a la vista de lista y filtros
    list_display = ('display_name', 'user', 'city', 'country', 'get_plan_name', 'get_subscription_status', 'is_active')
    list_filter = ('city', 'country', 'business_type', 'is_active', 'service_delivery_type', 'subscription__plan', 'subscription__status')
    search_fields = ('display_name', 'user__email', 'slug', 'city') # Añadido city a la búsqueda
    readonly_fields = ('created_at', 'slug')
    fieldsets = (
        ('Información Principal', {'fields': ('user', 'display_name', 'slug', 'photo', 'bio')}),
        # Añadimos city y country a la configuración del negocio
        ('Configuración del Negocio', {'fields': ('location_name', 'address', 'city', 'country', 'is_active', 'business_type')}),
        ('Configuración de Servicios y Domicilio', {'fields': ('service_delivery_type', 'travel_buffer', 'service_zones')}),
        ('Personalización Visual', {'fields': ('primary_color', 'secondary_color'), 'classes': ('collapse',)}),
    )
    inlines = [SubscriptionInline]
    filter_horizontal = ('service_zones',)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ('business_type',)
        return self.readonly_fields

    @admin.display(description='Plan Actual')
    def get_plan_name(self, obj):
        return obj.subscription.plan.name if hasattr(obj, 'subscription') and obj.subscription and obj.subscription.plan else 'N/A'

    @admin.display(description='Estado Suscripción')
    def get_subscription_status(self, obj):
        return obj.subscription.get_status_display() if hasattr(obj, 'subscription') and obj.subscription else 'N/A'

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
        ('Información de Contacto', {'fields': ('user', 'business', 'first_name', 'last_name', 'email', 'phone_number')}),
        ('Información de Domicilio', {'fields': ('address_line', 'latitude', 'longitude')}),
    )

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price_monthly', 'max_staff', 'allow_payments', 'is_active') # Asegúrate que `allow_whatsapp_reminders` esté aquí si lo añadiste
    list_filter = ('is_active',)

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('business', 'plan', 'status', 'trial_end_date', 'current_period_end')
    list_filter = ('plan', 'status')
    search_fields = ('business__display_name',)
    readonly_fields = ('created_at', 'updated_at')

# --- NUEVO REGISTRO ADMIN ---
@admin.register(ServiceZone)
class ServiceZoneAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)