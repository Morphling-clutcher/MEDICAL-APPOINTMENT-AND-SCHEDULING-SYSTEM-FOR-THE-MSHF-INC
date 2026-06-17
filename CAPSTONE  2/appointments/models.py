from django.db import models
from django.conf import settings


class Schedule(models.Model):
    DAY_CHOICES = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
    ]
    doctor      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='schedules', limit_choices_to={'role': 'doctor'}
    )
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time  = models.TimeField()
    end_time    = models.TimeField()

    class Meta:
        unique_together = ('doctor', 'day_of_week', 'start_time')
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        return f"Dr. {self.doctor.get_full_name()} — {self.get_day_of_week_display()} {self.start_time.strftime('%I:%M %p')}–{self.end_time.strftime('%I:%M %p')}"


class Appointment(models.Model):
    STATUS_CHOICES = [
        ('Scheduled',   'Scheduled'),
        ('Completed',   'Completed'),
        ('Cancelled',   'Cancelled'),
        ('Rescheduled', 'Rescheduled'),
    ]
    patient          = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='patient_appointments', limit_choices_to={'role': 'patient'}
    )
    doctor           = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='doctor_appointments', limit_choices_to={'role': 'doctor'}
    )
    secretary        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='secretary_appointments',
        limit_choices_to={'role': 'secretary'}
    )
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Scheduled')
    reason           = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['appointment_date', 'appointment_time']

    def __str__(self):
        return f"{self.patient.get_full_name()} + Dr. {self.doctor.get_full_name()} on {self.appointment_date} [{self.status}]"
