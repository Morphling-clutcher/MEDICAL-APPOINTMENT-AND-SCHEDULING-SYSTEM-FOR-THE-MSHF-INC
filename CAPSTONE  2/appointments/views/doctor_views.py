from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from datetime import date
from accounts.decorators import role_required
from appointments.models import Appointment, Schedule
from appointments.forms import ScheduleForm, RescheduleForm
from accounts.models import CustomUser
from notifications.email_utils import send_cancellation_email, send_reschedule_email
from notifications.models import Notification


def _notify(user, message):
    Notification.objects.create(user=user, message=message)


@role_required('doctor')
def doctor_dashboard(request):
    today_appts = Appointment.objects.filter(
        doctor=request.user,
        appointment_date=date.today(),
        status__in=['Scheduled', 'Rescheduled']
    ).select_related('patient').order_by('appointment_time')
    upcoming = Appointment.objects.filter(
        doctor=request.user,
        appointment_date__gt=date.today(),
        status__in=['Scheduled', 'Rescheduled']
    ).count()
    return render(request, 'doctor/dashboard.html', {
        'today_appts': today_appts, 'upcoming_count': upcoming
    })


@role_required('doctor')
def schedule_list(request):
    schedules = Schedule.objects.filter(doctor=request.user)
    return render(request, 'doctor/schedule_list.html', {'schedules': schedules})


@role_required('doctor')
def schedule_add(request):
    form = ScheduleForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        schedule = form.save(commit=False)
        schedule.doctor = request.user
        # Check overlap
        overlap = Schedule.objects.filter(
            doctor=request.user,
            day_of_week=schedule.day_of_week,
            start_time__lt=schedule.end_time,
            end_time__gt=schedule.start_time,
        ).exists()
        if overlap:
            messages.error(request, 'This schedule overlaps with an existing one.')
        else:
            schedule.save()
            messages.success(request, 'Schedule slot added.')
            return redirect('doctor:schedule_list')
    return render(request, 'doctor/schedule_form.html', {'form': form, 'action': 'Add'})


@role_required('doctor')
def schedule_edit(request, pk):
    schedule = get_object_or_404(Schedule, pk=pk, doctor=request.user)
    form = ScheduleForm(request.POST or None, instance=schedule)
    if request.method == 'POST' and form.is_valid():
        updated = form.save(commit=False)
        overlap = Schedule.objects.filter(
            doctor=request.user,
            day_of_week=updated.day_of_week,
            start_time__lt=updated.end_time,
            end_time__gt=updated.start_time,
        ).exclude(pk=pk).exists()
        if overlap:
            messages.error(request, 'This schedule overlaps with an existing one.')
        else:
            updated.save()
            messages.success(request, 'Schedule updated.')
            return redirect('doctor:schedule_list')
    return render(request, 'doctor/schedule_form.html', {'form': form, 'action': 'Edit'})


@role_required('doctor')
def schedule_delete(request, pk):
    schedule = get_object_or_404(Schedule, pk=pk, doctor=request.user)
    if request.method == 'POST':
        schedule.delete()
        messages.success(request, 'Schedule slot removed.')
        return redirect('doctor:schedule_list')
    return render(request, 'doctor/schedule_confirm_delete.html', {'schedule': schedule})


@role_required('doctor')
def doctor_appointment_list(request):
    status_filter = request.GET.get('status', '')
    qs = Appointment.objects.filter(doctor=request.user).select_related('patient')
    if status_filter:
        qs = qs.filter(status=status_filter)
    return render(request, 'doctor/appointment_list.html', {
        'appointments': qs, 'status_filter': status_filter
    })


@role_required('doctor')
def appointment_accept(request, pk):
    appt = get_object_or_404(Appointment, pk=pk, doctor=request.user, status='Scheduled')
    if request.method == 'POST':
        _notify(appt.patient,
                f"Dr. {request.user.get_full_name()} has confirmed your appointment on "
                f"{appt.appointment_date.strftime('%B %d, %Y')} at {appt.appointment_time.strftime('%I:%M %p')}.")
        messages.success(request, 'Appointment confirmed.')
        return redirect('doctor:appointment_list')
    return render(request, 'doctor/appointment_confirm_action.html', {
        'appointment': appt, 'action': 'accept'
    })


@role_required('doctor')
def appointment_decline(request, pk):
    appt = get_object_or_404(Appointment, pk=pk, doctor=request.user, status__in=['Scheduled', 'Rescheduled'])
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        appt.status = 'Cancelled'
        appt.save()
        try:
            send_cancellation_email(appt, reason)
        except Exception:
            pass
        _notify(appt.patient,
                f"Dr. {request.user.get_full_name()} has cancelled your appointment on "
                f"{appt.appointment_date.strftime('%B %d, %Y')}.")
        messages.success(request, 'Appointment declined and patient notified.')
        return redirect('doctor:appointment_list')
    return render(request, 'doctor/appointment_confirm_action.html', {
        'appointment': appt, 'action': 'decline'
    })


@role_required('doctor')
def appointment_reschedule(request, pk):
    appt = get_object_or_404(Appointment, pk=pk, doctor=request.user, status__in=['Scheduled', 'Rescheduled'])
    from django.db import transaction
    from datetime import datetime
    form = RescheduleForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        new_date = form.cleaned_data['appointment_date']
        new_time = form.cleaned_data['appointment_time']
        with transaction.atomic():
            conflict = Appointment.objects.select_for_update().filter(
                doctor=request.user,
                appointment_date=new_date,
                appointment_time=new_time,
                status__in=['Scheduled', 'Rescheduled']
            ).exclude(pk=appt.pk).exists()
            if conflict:
                messages.error(request, 'That slot is already taken.')
            else:
                appt.status = 'Rescheduled'
                appt.save()
                new_appt = Appointment.objects.create(
                    patient=appt.patient, doctor=request.user,
                    appointment_date=new_date, appointment_time=new_time,
                    status='Scheduled', reason=appt.reason
                )
        if not conflict:
            try:
                send_reschedule_email(new_appt)
            except Exception:
                pass
            _notify(appt.patient,
                    f"Dr. {request.user.get_full_name()} rescheduled your appointment to "
                    f"{new_date.strftime('%B %d, %Y')} at {new_time.strftime('%I:%M %p')}.")
            messages.success(request, 'Appointment rescheduled.')
            return redirect('doctor:appointment_list')
    return render(request, 'doctor/appointment_reschedule.html', {'form': form, 'appointment': appt})


@role_required('doctor')
def appointment_complete(request, pk):
    appt = get_object_or_404(Appointment, pk=pk, doctor=request.user, status__in=['Scheduled', 'Rescheduled'])
    if request.method == 'POST':
        appt.status = 'Completed'
        appt.save()
        messages.success(request, 'Appointment marked as completed.')
        return redirect('doctor:add_results', pk=appt.pk)
    return render(request, 'doctor/appointment_confirm_action.html', {
        'appointment': appt, 'action': 'complete'
    })


@role_required('doctor')
def add_consultation_results(request, pk):
    appt = get_object_or_404(Appointment, pk=pk, doctor=request.user, status='Completed')
    from records.models import ResultsConsultation, MedicalRecords
    from records.forms import ResultsConsultationForm
    existing = getattr(appt, 'results', None)
    form = ResultsConsultationForm(request.POST or None, instance=existing)
    if request.method == 'POST' and form.is_valid():
        result = form.save(commit=False)
        result.appointment = appt
        result.save()
        MedicalRecords.objects.get_or_create(
            doctor=request.user, patient=appt.patient,
            results=result, defaults={'visit_date': appt.appointment_date}
        )
        messages.success(request, 'Consultation results saved.')
        return redirect('doctor:add_prescription', pk=appt.pk)
    return render(request, 'doctor/consultation_form.html', {
        'form': form, 'appointment': appt, 'existing': existing
    })


@role_required('doctor')
def add_prescription(request, pk):
    appt = get_object_or_404(Appointment, pk=pk, doctor=request.user)
    from records.models import ResultsConsultation, Prescription
    from records.forms import PrescriptionForm
    try:
        results = appt.results
    except ResultsConsultation.DoesNotExist:
        messages.error(request, 'Please add consultation results first.')
        return redirect('doctor:add_results', pk=pk)
    form = PrescriptionForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        prescription = form.save(commit=False)
        prescription.results_consultation = results
        prescription.save()
        messages.success(request, 'Prescription saved.')
        return redirect('doctor:appointment_list')
    prescriptions = results.prescriptions.all()
    return render(request, 'doctor/prescription_form.html', {
        'form': form, 'appointment': appt, 'prescriptions': prescriptions
    })


@role_required('doctor')
def doctor_patient_list(request):
    from django.db.models import Max
    patient_ids = Appointment.objects.filter(
        doctor=request.user
    ).values_list('patient_id', flat=True).distinct()
    patients = CustomUser.objects.filter(pk__in=patient_ids)
    return render(request, 'doctor/patient_list.html', {'patients': patients})


@role_required('doctor')
def doctor_patient_records(request, patient_id):
    # Doctor may only view records for patients who have had appointments with them
    patient = get_object_or_404(CustomUser, pk=patient_id, role='patient')
    has_appt = Appointment.objects.filter(doctor=request.user, patient=patient).exists()
    if not has_appt:
        messages.error(request, 'You do not have access to this patient.')
        return redirect('doctor:patient_list')
    from records.models import MedicalRecords, VitalSign
    records   = MedicalRecords.objects.filter(patient=patient).select_related('results', 'doctor')
    vitals    = VitalSign.objects.filter(patient=patient)
    return render(request, 'doctor/patient_records.html', {
        'patient': patient, 'records': records, 'vitals': vitals
    })


@role_required('doctor')
def doctor_notifications(request):
    return redirect('/notifications/')
