from django.contrib import admin
from .models import AvailabilityRule, Appointment

@admin.register(AvailabilityRule)
class AvailabilityRuleAdmin(admin.ModelAdmin):
    list_display = ('client', 'get_day_of_week_display', 'start_time', 'end_time')
    list_filter = ('client',)
    # Muestra el nombre del día en lugar del número
    def get_day_of_week_display(self, obj):
        return obj.get_day_of_week_display()
    get_day_of_week_display.short_description = 'Día de la Semana'


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'client', 'service', 'start_time', 'status')
    list_filter = ('status', 'client')
    search_fields = ('customer__first_name', 'client__display_name', 'service__name')
    readonly_fields = ('created_at',)