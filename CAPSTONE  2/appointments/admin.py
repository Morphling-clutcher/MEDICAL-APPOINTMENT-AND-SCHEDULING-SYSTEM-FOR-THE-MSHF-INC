from django.contrib import admin
from .models import Schedule, Appointment


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ['doctor', 'day_of_week', 'start_time', 'end_time']
    list_filter  = ['day_of_week', 'doctor']


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display  = ['patient', 'doctor', 'appointment_date', 'appointment_time', 'status']
    list_filter   = ['status', 'appointment_date']
    search_fields = ['patient__first_name', 'patient__last_name', 'doctor__last_name']
