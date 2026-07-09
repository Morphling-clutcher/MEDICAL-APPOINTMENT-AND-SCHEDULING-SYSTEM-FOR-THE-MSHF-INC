from datetime import date, timedelta
from django import forms
from .models import VitalSign, ResultsConsultation, Prescription

ALLOWED_ATTACHMENT_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.pdf')
MAX_ATTACHMENT_SIZE_MB = 5

# Vitals are always taken at the actual visit, never backdated by weeks
# or months — this bounds how far back "Date Taken" can go. (Whether it
# should be locked/read-only to today entirely is still an open
# question — flagged for follow-up, not decided here.)
VITALS_BACKDATE_WINDOW_DAYS = 7


class VitalSignForm(forms.ModelForm):
    class Meta:
        model   = VitalSign
        fields  = ['bp', 'weight', 'date_taken']
        widgets = {'date_taken': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = date.today()
        earliest = today - timedelta(days=VITALS_BACKDATE_WINDOW_DAYS)
        # Bounds the native date picker itself (can't scroll to a future
        # date, or all the way back to e.g. 2005) and, combined with the
        # narrow range, makes an accidental 6-digit year immediately
        # fall outside min/max instead of silently being accepted.
        self.fields['date_taken'].widget.attrs['min'] = earliest.isoformat()
        self.fields['date_taken'].widget.attrs['max'] = today.isoformat()
        if not self.is_bound and not (self.instance and self.instance.pk) and not self.initial.get('date_taken'):
            self.initial['date_taken'] = today.isoformat()

    def clean_date_taken(self):
        # Belt-and-suspenders: the widget's min/max only guard the
        # picker UI. A manually-typed value (or a directly-posted
        # request) must still be rejected here — this is what actually
        # stops a stray 6-digit year or an old date like 2005 from ever
        # being saved, regardless of what the browser let through.
        d = self.cleaned_data.get('date_taken')
        if not d:
            return d
        today = date.today()
        if d > today:
            raise forms.ValidationError('Date taken cannot be in the future.')
        if d < today - timedelta(days=VITALS_BACKDATE_WINDOW_DAYS):
            raise forms.ValidationError(
                f'Date taken cannot be more than {VITALS_BACKDATE_WINDOW_DAYS} days in the past.'
            )
        return d


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
            'medication_names': forms.Textarea(attrs={'rows': 3, 'placeholder': 'e.g. Amoxicillin 500mg — 3x daily for 7 days'}),
            'notes':            forms.Textarea(attrs={'rows': 3, 'placeholder': 'e.g. Patient presented with mild fever and sore throat for 3 days. No signs of respiratory distress. Advised rest and hydration.'}),
            'treatment':        forms.Textarea(attrs={'rows': 3, 'placeholder': 'e.g. Rest for 3–5 days, increase fluid intake, monitor temperature. Return if fever persists beyond 3 days.'}),
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
