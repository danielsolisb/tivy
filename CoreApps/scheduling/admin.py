from django.contrib import admin
from .models import AvailabilityBlock, Appointment

@admin.register(AvailabilityBlock)
class AvailabilityBlockAdmin(admin.ModelAdmin):
    list_display = ('staff_member', 'start_time', 'end_time')
    list_filter = ('staff_member__business', 'staff_member')
    date_hierarchy = 'start_time'

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'business', 'staff_member', 'service', 'start_time', 'status')
    list_filter = ('status', 'business', 'staff_member')
    search_fields = ('customer__first_name', 'business__display_name', 'staff_member__name')
    readonly_fields = ('created_at',)