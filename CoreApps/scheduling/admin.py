from django.contrib import admin
from .models import AvailabilityBlock, Appointment # Cambiamos la importación

@admin.register(AvailabilityBlock)
class AvailabilityBlockAdmin(admin.ModelAdmin):
    list_display = ('client', 'start_time', 'end_time')
    list_filter = ('client',)
    date_hierarchy = 'start_time' # Permite navegar por fechas fácilmente

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'client', 'service', 'start_time', 'status')
    list_filter = ('status', 'client')
    search_fields = ('customer__first_name', 'client__display_name', 'service__name')
    readonly_fields = ('created_at',)