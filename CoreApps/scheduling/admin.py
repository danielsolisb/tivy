# CoreApps/scheduling/admin.py

from django.contrib import admin
# Añadimos TimeOffBlock a la importación
from .models import AvailabilityBlock, Appointment, TimeOffBlock 

@admin.register(AvailabilityBlock)
class AvailabilityBlockAdmin(admin.ModelAdmin):
    # Añadimos staff_can_edit a la lista
    list_display = ('staff_member', 'start_time', 'end_time', 'staff_can_edit')
    list_filter = ('staff_member__business', 'staff_member', 'staff_can_edit')
    date_hierarchy = 'start_time'
    # Hacemos el campo editable directamente en la lista (opcional)
    list_editable = ('staff_can_edit',) 

# --- NUEVO REGISTRO ADMIN ---
@admin.register(TimeOffBlock)
class TimeOffBlockAdmin(admin.ModelAdmin):
    list_display = ('staff_member', 'start_time', 'end_time', 'reason')
    list_filter = ('staff_member__business', 'staff_member')
    date_hierarchy = 'start_time'
    search_fields = ('reason', 'staff_member__name')

# AppointmentAdmin sin cambios en este paso
@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'business', 'staff_member', 'service', 'start_time', 'status')
    list_filter = ('status', 'business', 'staff_member')
    search_fields = ('customer__first_name', 'business__display_name', 'staff_member__name')
    readonly_fields = ('created_at',)