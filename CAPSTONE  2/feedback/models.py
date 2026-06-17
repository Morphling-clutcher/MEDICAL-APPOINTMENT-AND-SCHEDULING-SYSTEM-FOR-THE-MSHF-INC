from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class Feedback(models.Model):
    patient        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='feedback', limit_choices_to={'role': 'patient'}
    )
    appointment    = models.ForeignKey(
        'appointments.Appointment', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='feedback'
    )
    rating         = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment        = models.TextField(blank=True)
    date_submitted = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_submitted']

    def __str__(self):
        return f"Feedback by {self.patient.get_full_name()} — {self.rating}/5"
