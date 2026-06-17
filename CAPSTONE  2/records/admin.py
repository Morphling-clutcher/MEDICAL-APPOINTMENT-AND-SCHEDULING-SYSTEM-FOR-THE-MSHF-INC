from django.contrib import admin
from .models import VitalSign, ResultsConsultation, Prescription, MedicalRecords

admin.site.register(VitalSign)
admin.site.register(ResultsConsultation)
admin.site.register(Prescription)
admin.site.register(MedicalRecords)
