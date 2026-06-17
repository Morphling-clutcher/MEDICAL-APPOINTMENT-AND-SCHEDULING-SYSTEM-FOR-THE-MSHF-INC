from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('patient',   'Patient'),
        ('doctor',    'Doctor'),
        ('secretary', 'Secretary'),
        ('admin',     'Admin'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='patient')

    def is_patient(self):    return self.role == 'patient'
    def is_doctor(self):     return self.role == 'doctor'
    def is_secretary(self):  return self.role == 'secretary'
    def is_admin_role(self): return self.role == 'admin'

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.role})"


class PatientProfile(models.Model):
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female'), ('O', 'Other')]
    user           = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='patient_profile')
    contact_number = models.CharField(max_length=20, blank=True)
    age            = models.PositiveIntegerField(null=True, blank=True)
    gender         = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    date_of_birth  = models.DateField(null=True, blank=True)
    place_of_birth = models.CharField(max_length=150, blank=True)
    address        = models.TextField(blank=True)
    guardian       = models.CharField(max_length=150, blank=True)

    def __str__(self):
        return f"Profile: {self.user.get_full_name()}"


class DoctorProfile(models.Model):
    user           = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='doctor_profile')
    specialization = models.CharField(max_length=150, blank=True)

    def __str__(self):
        return f"Dr. {self.user.get_full_name()} — {self.specialization}"


class SecretaryProfile(models.Model):
    user            = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='secretary_profile')
    assigned_doctor = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_secretaries',
        limit_choices_to={'role': 'doctor'}
    )
    date_assigned   = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Secretary: {self.user.get_full_name()}"
