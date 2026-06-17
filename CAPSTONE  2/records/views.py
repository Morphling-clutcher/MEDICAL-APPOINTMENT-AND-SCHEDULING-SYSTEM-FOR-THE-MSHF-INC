from django.shortcuts import render, get_object_or_404
from accounts.decorators import role_required
from accounts.models import CustomUser
from .models import MedicalRecords, VitalSign


@role_required('patient', 'doctor', 'secretary', 'admin')
def patient_records_view(request, patient_id):
    patient = get_object_or_404(CustomUser, pk=patient_id, role='patient')
    if request.user.role == 'patient' and request.user.pk != patient_id:
        from django.shortcuts import redirect
        from django.contrib import messages
        messages.error(request, 'Access denied.')
        return redirect('landing')
    records = MedicalRecords.objects.filter(patient=patient).select_related('results', 'doctor')
    vitals  = VitalSign.objects.filter(patient=patient).order_by('-date_taken')
    return render(request, 'patient/medical_records.html', {
        'patient': patient, 'records': records, 'vitals': vitals
    })
