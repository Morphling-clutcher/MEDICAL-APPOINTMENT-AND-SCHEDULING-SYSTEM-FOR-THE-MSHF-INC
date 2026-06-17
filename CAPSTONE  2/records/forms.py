from django import forms
from .models import VitalSign, ResultsConsultation, Prescription


class VitalSignForm(forms.ModelForm):
    class Meta:
        model   = VitalSign
        fields  = ['bp', 'weight', 'date_taken']
        widgets = {'date_taken': forms.DateInput(attrs={'type': 'date'})}


class ResultsConsultationForm(forms.ModelForm):
    class Meta:
        model  = ResultsConsultation
        fields = ['diagnosis']
        widgets = {'diagnosis': forms.Textarea(attrs={'rows': 5})}


class PrescriptionForm(forms.ModelForm):
    class Meta:
        model  = Prescription
        fields = ['date_issued', 'medication_names', 'notes', 'treatment']
        widgets = {
            'date_issued':      forms.DateInput(attrs={'type': 'date'}),
            'medication_names': forms.Textarea(attrs={'rows': 3}),
            'notes':            forms.Textarea(attrs={'rows': 3}),
            'treatment':        forms.Textarea(attrs={'rows': 3}),
        }
