from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from datetime import date
from accounts.decorators import role_required
from appointments.models import Appointment, Schedule
from accounts.models import CustomUser, PatientProfile
from notifications.email_utils import send_cancellation_email
from notifications.models import Notification


def _notify(user, message):
    Notification.objects.create(user=user, message=message)


@role_required('secretary')
def secretary_dashboard(request):
    today_appts = Appointment.objects.filter(
        appointment_date=date.today(),
        status__in=['Scheduled', 'Rescheduled']
    ).select_related('patient', 'doctor').order_by('appointment_time')
    total_today = today_appts.count()

    dashboard_data = {
        'stats': [
            {'label': "Today's Appointments", 'value': total_today},
        ],
        'appointmentsTitle': "Today's Appointments",
        'appointmentsHref': '/secretary/appointments/',
        'appointments': [
            {
                'primary': a.patient.get_full_name(),
                'secondary': f'Dr. {a.doctor.get_full_name()}',
                'date': a.appointment_date.isoformat(),
                'time': a.appointment_time.strftime('%H:%M'),
                'status': a.status,
            }
            for a in today_appts
        ],
        'quickActions': [
            {'title': 'Appointments', 'description': 'Approve or cancel requests', 'href': '/secretary/appointments/'},
            {'title': 'Walk-In Registration', 'description': 'Register a walk-in patient', 'href': '/secretary/walk-in/register/'},
            {'title': 'Schedules', 'description': 'View doctor schedules', 'href': '/secretary/schedules/'},
            {'title': 'Patients', 'description': 'View patient list', 'href': '/secretary/patients/'},
        ],
    }
    return render(request, 'secretary/dashboard.html', {'dashboard_data': dashboard_data})


@role_required('secretary')
def secretary_appointment_list(request):
    status_filter = request.GET.get('status', '')
    date_filter   = request.GET.get('date', '')
    qs = Appointment.objects.all().select_related('patient', 'doctor')
    if status_filter:
        qs = qs.filter(status=status_filter)
    if date_filter:
        qs = qs.filter(appointment_date=date_filter)
    return render(request, 'secretary/appointment_list.html', {
        'appointments': qs.order_by('appointment_date', 'appointment_time'),
        'status_filter': status_filter, 'date_filter': date_filter,
    })


@role_required('secretary')
def appointment_approve(request, pk):
    appt = get_object_or_404(Appointment, pk=pk, status='Scheduled')
    if request.method == 'POST':
        appt.secretary = request.user
        appt.save()
        _notify(appt.patient,
                f"Your appointment with Dr. {appt.doctor.get_full_name()} on "
                f"{appt.appointment_date.strftime('%B %d, %Y')} has been confirmed by the secretary.")
        messages.success(request, 'Appointment approved.')
        return redirect('secretary:appointment_list')
    return render(request, 'secretary/appointment_confirm_action.html', {
        'appointment': appt, 'action': 'approve'
    })


@role_required('secretary')
def appointment_cancel(request, pk):
    appt = get_object_or_404(Appointment, pk=pk, status__in=['Scheduled', 'Rescheduled'])
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        appt.status = 'Cancelled'
        appt.secretary = request.user
        appt.save()
        try:
            send_cancellation_email(appt, reason)
        except Exception:
            pass
        _notify(appt.patient,
                f"Your appointment with Dr. {appt.doctor.get_full_name()} on "
                f"{appt.appointment_date.strftime('%B %d, %Y')} was cancelled.")
        messages.success(request, 'Appointment cancelled and patient notified.')
        return redirect('secretary:appointment_list')
    return render(request, 'secretary/appointment_confirm_action.html', {
        'appointment': appt, 'action': 'cancel'
    })


@role_required('secretary')
def walkin_register(request):
    from accounts.forms import PatientRegistrationForm
    form = PatientRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        messages.success(request, f'Walk-in patient {user.get_full_name()} registered.')
        return redirect('secretary:vitals_add', patient_id=user.pk)
    return render(request, 'secretary/walkin_register.html', {'form': form})


@role_required('secretary')
def vitals_add(request, patient_id):
    patient = get_object_or_404(CustomUser, pk=patient_id, role='patient')
    from records.forms import VitalSignForm
    from records.models import VitalSign
    form = VitalSignForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        vital = form.save(commit=False)
        vital.patient   = patient
        vital.secretary = request.user
        vital.save()
        messages.success(request, 'Vital signs recorded.')
        return redirect('secretary:patient_records', patient_id=patient.pk)
    vitals = VitalSign.objects.filter(patient=patient).order_by('-date_taken')
    return render(request, 'secretary/vitals_form.html', {
        'form': form, 'patient': patient, 'vitals': vitals
    })


@role_required('secretary')
def view_all_schedules(request):
    schedules = Schedule.objects.all().select_related('doctor').order_by('doctor', 'day_of_week', 'start_time')
    doctors   = CustomUser.objects.filter(role='doctor')
    return render(request, 'secretary/schedules.html', {
        'schedules': schedules, 'doctors': doctors
    })


@role_required('secretary')
def secretary_patient_list(request):
    search = request.GET.get('q', '')
    patients = CustomUser.objects.filter(role='patient')
    if search:
        patients = patients.filter(
            first_name__icontains=search
        ) | CustomUser.objects.filter(role='patient', last_name__icontains=search)
    return render(request, 'secretary/patient_list.html', {
        'patients': patients.distinct(), 'search': search
    })


@role_required('secretary')
def secretary_patient_records(request, patient_id):
    patient = get_object_or_404(CustomUser, pk=patient_id, role='patient')
    from records.models import MedicalRecords, VitalSign
    records = MedicalRecords.objects.filter(patient=patient).select_related('results', 'doctor')
    vitals  = VitalSign.objects.filter(patient=patient).order_by('-date_taken')
    appts   = Appointment.objects.filter(patient=patient).select_related('doctor').order_by('-appointment_date')
    return render(request, 'secretary/patient_records.html', {
        'patient': patient, 'records': records, 'vitals': vitals, 'appts': appts
    })


@role_required('secretary')
def secretary_notifications(request):
    return redirect('/notifications/')
