from django.db import models
from django.conf import settings


class VitalSign(models.Model):
    patient    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='vital_signs', limit_choices_to={'role': 'patient'}
    )
    secretary  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='recorded_vitals',
        limit_choices_to={'role': 'secretary'}
    )
    bp         = models.CharField(max_length=20, verbose_name='Blood Pressure')
    weight     = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Weight (kg)')
    date_taken = models.DateField()

    class Meta:
        ordering = ['-date_taken']

    def __str__(self):
        return f"Vitals for {self.patient.get_full_name()} on {self.date_taken}"


class ResultsConsultation(models.Model):
    appointment = models.OneToOneField(
        'appointments.Appointment', on_delete=models.CASCADE, related_name='results'
    )
    diagnosis   = models.TextField()
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Results for Appt #{self.appointment_id}"


class Prescription(models.Model):
    results_consultation = models.ForeignKey(
        ResultsConsultation, on_delete=models.CASCADE, related_name='prescriptions'
    )
    date_issued      = models.DateField()
    medication_names = models.TextField()
    notes            = models.TextField(blank=True)
    treatment        = models.TextField(blank=True)
    attachment       = models.FileField(
        upload_to='prescriptions/%Y/%m/', null=True, blank=True,
        help_text='Optional: photo or scan of a handwritten prescription, lab result, or referral (JPG, PNG, or PDF).'
    )

    def __str__(self):
        return f"Prescription #{self.pk} — {self.date_issued}"

    @property
    def attachment_is_image(self):
        if not self.attachment:
            return False
        name = self.attachment.name.lower()
        return name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))


class MedicalRecords(models.Model):
    doctor     = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='medical_records_doctor', limit_choices_to={'role': 'doctor'}
    )
    patient    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='medical_records_patient', limit_choices_to={'role': 'patient'}
    )
    results    = models.ForeignKey(
        ResultsConsultation, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='medical_records'
    )
    visit_date = models.DateField()

    class Meta:
        ordering = ['-visit_date']

    def __str__(self):
        return f"Record: {self.patient.get_full_name()} — {self.visit_date}"
