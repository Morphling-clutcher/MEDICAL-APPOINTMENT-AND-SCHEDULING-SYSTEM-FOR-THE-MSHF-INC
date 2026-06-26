from django import forms
from .models import VitalSign, ResultsConsultation, Prescription

ALLOWED_ATTACHMENT_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.pdf')
MAX_ATTACHMENT_SIZE_MB = 5


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
        fields = ['date_issued', 'medication_names', 'notes', 'treatment', 'attachment']
        widgets = {
            'date_issued':      forms.DateInput(attrs={'type': 'date'}),
            'medication_names': forms.Textarea(attrs={'rows': 3}),
            'notes':            forms.Textarea(attrs={'rows': 3}),
            'treatment':        forms.Textarea(attrs={'rows': 3}),
            'attachment':       forms.ClearableFileInput(attrs={'accept': '.jpg,.jpeg,.png,.pdf'}),
        }

    def clean_attachment(self):
        f = self.cleaned_data.get('attachment')
        if not f:
            return f
        # Only re-validate newly uploaded files; an already-saved FieldFile
        # has no content_type and would otherwise fail this check on every
        # subsequent edit even when the file itself wasn't touched.
        if not hasattr(f, 'content_type'):
            return f
        name = f.name.lower()
        if not name.endswith(ALLOWED_ATTACHMENT_EXTENSIONS):
            raise forms.ValidationError('Only JPG, PNG, or PDF files are allowed.')
        if f.size > MAX_ATTACHMENT_SIZE_MB * 1024 * 1024:
            raise forms.ValidationError(f'File is too large (max {MAX_ATTACHMENT_SIZE_MB}MB).')
        return f
